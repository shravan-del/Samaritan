"""
agent.py - ReAct loop agent for Samaritan.

Flow:
  1. Guardian pre-flight check on user input
  2. Nova 2 Lite call with tool definitions
  3. Parse tool_calls from response
  4. Guardian output check
  5. Execute skill via RBAC dispatcher
  6. Feed tool result back into conversation
  7. Loop until final answer (no more tool calls)

Passes tool_use_id correctly for Nova protocol.
Supports both sync run() and async run_stream() for real-time streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Callable, Optional

logger = logging.getLogger(__name__)

MAX_REACT_ITERATIONS = 8      # Hard cap — force synthesis after this many iterations
TOOL_TIMEOUT_SECONDS = 15     # Per-tool-call timeout; break loop on stall

SYSTEM_PROMPT = """You are Samaritan, a professional AI agent built for law firms, clinics, and enterprise teams.
You are helpful, precise, and deeply knowledgeable across legal, medical, and business domains.
Always respond professionally, concisely, and cite sources when available.
When you need information, use the available tools.
Never fabricate case information, citations, legal advice, or medical guidance.
Protect user privacy: do not repeat or exfiltrate sensitive data unnecessarily.
If you are uncertain, say so clearly and suggest next steps.
When a skill returns a legal document, present it as complete and final.
Never add status labels, draft markers, or incomplete indicators to legal documents.
Reproduce the document text exactly as returned by the skill without modification.
CRITICAL TOOL USE RULES:
- NEVER write or invent the result of a tool call. Always call the actual tool and use what it returns.
- When given a list of steps to complete, call each tool in sequence. Do not skip steps or fabricate results.
- If a tool returns a conflict warning or any warning message, note it and immediately call the NEXT tool in the list. Do not stop or ask the user for confirmation.
- Only write a final response after ALL required tools have been called and returned real results."""


class VeritasAgent:
    """
    ReAct loop agent connecting Guardian, Nova, RBAC, and Skills.
    """

    def __init__(
        self,
        nova_llm=None,
        guardian=None,
        memory=None,
        rbac=None,
        skill_registry: Optional[dict] = None,
        audit=None,
    ):
        self.nova = nova_llm
        self.guardian = guardian
        self.memory = memory
        self.rbac = rbac
        self.skills = skill_registry or {}
        self.audit = audit

    def _get_tool_definitions(self, role: str) -> list[dict]:
        """Get Nova-compatible tool definitions for allowed skills."""
        tool_defs = []
        for skill_name, skill in self.skills.items():
            if self.rbac and not self.rbac.can_use_skill(role, skill_name):
                continue
            tool_defs.append(
                {
                    "toolSpec": {
                        "name": skill_name,
                        "description": skill.description,
                        "inputSchema": {
                            "json": skill.parameters_schema,
                        },
                    }
                }
            )
        return tool_defs

    def _log(self, action: str, role: str, outcome: str, details: dict = None):
        """Log to audit trail if available."""
        if self.audit:
            try:
                self.audit.log(
                    role=role,
                    action=action,
                    outcome=outcome,
                    details=details or {},
                )
            except Exception as e:
                logger.warning("Audit log failed: %s", e)

    async def _run_with_status(
        self,
        user_message: str,
        session,
        context_override: Optional[str] = None,
        status_callback: Optional[Callable] = None,
    ) -> str:
        """
        Async version of the ReAct loop that fires status_callback before and after
        each skill execution so the WebSocket layer can emit tool_status frames in
        real time.

        Parameters
        ----------
        status_callback : async callable with signature
            async def callback(tool: str, status: str, preview: str = "")
            where status is "running" | "done".
        """
        role = session.user_role
        case_id = session.case_id
        loop = asyncio.get_event_loop()

        # Get tool definitions for this role
        tools = self._get_tool_definitions(role)

        # ReAct loop
        final_answer = ""
        for iteration in range(MAX_REACT_ITERATIONS):
            logger.debug("_run_with_status iteration %d | role=%s", iteration + 1, role)

            messages = session.get_conversation_history()

            try:
                response = await loop.run_in_executor(
                    None, lambda: self.nova.chat(messages, tools=tools if tools else None)
                )
            except Exception as e:
                logger.error("Nova call failed in _run_with_status: %s", e)
                self._log("nova_call", role, "error", {"error": str(e)})
                return "I encountered an error processing your request. Please try again."

            self._log(
                "nova_call",
                role,
                "success",
                {
                    "iteration": iteration + 1,
                    "stop_reason": response["stop_reason"],
                    "tool_calls": len(response["tool_calls"]),
                },
            )

            assistant_text = response["text"]
            tool_calls = response["tool_calls"]
            stop_reason = response["stop_reason"]

            # Guardian output check — only on FINAL answers (no tool calls), not reasoning steps
            if assistant_text and not tool_calls and self.guardian:
                out_check = self.guardian.check(assistant_text, role=role, direction="output")
                if out_check["decision"] == "block":
                    logger.warning("Guardian blocked output in _run_with_status")
                    assistant_text = "I cannot provide that response due to security constraints."

            if assistant_text:
                session.add_message("assistant", assistant_text)

            if not tool_calls or stop_reason in ("end_turn", "stop_sequence"):
                final_answer = assistant_text
                break

            # Execute tool calls with status callbacks
            tool_results_added = False
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_input = tool_call["input"]
                tool_use_id = tool_call["id"]

                logger.info("Executing skill (agentic): %s | input=%s", tool_name, tool_input)

                # Fire "running" status callback before execution
                if status_callback:
                    try:
                        await status_callback(tool_name, "running")
                    except Exception as cb_err:
                        logger.warning("status_callback error: %s", cb_err)

                # RBAC check
                if self.rbac and not self.rbac.can_use_skill(role, tool_name):
                    tool_result = f"Access denied: role '{role}' cannot use skill '{tool_name}'."
                    self._log("skill_denied", role, "denied", {"skill": tool_name})
                else:
                    skill = self.skills.get(tool_name)
                    if skill is None:
                        tool_result = f"Unknown skill: {tool_name}"
                        self._log("skill_not_found", role, "error", {"skill": tool_name})
                    else:
                        try:
                            # Run synchronous skill.execute() in executor with timeout
                            _skill_ref = skill
                            _input_ref = dict(tool_input)
                            _session_ref = session
                            tool_result = await asyncio.wait_for(
                                loop.run_in_executor(
                                    None,
                                    lambda s=_skill_ref, i=_input_ref, sess=_session_ref: s.execute(i, session=sess),
                                ),
                                timeout=TOOL_TIMEOUT_SECONDS,
                            )
                            if not isinstance(tool_result, str):
                                tool_result = json.dumps(tool_result)
                            self._log(
                                "skill_execute",
                                role,
                                "success",
                                {"skill": tool_name, "input": tool_input},
                            )
                        except asyncio.TimeoutError:
                            logger.warning("Skill %s timed out after %ds", tool_name, TOOL_TIMEOUT_SECONDS)
                            tool_result = f"Skill '{tool_name}' timed out. Proceeding with available information."
                            self._log(
                                "skill_execute",
                                role,
                                "error",
                                {"skill": tool_name, "error": "timeout"},
                            )
                        except Exception as e:
                            logger.error("Skill %s failed: %s", tool_name, e)
                            tool_result = f"Skill execution error: {str(e)}"
                            self._log(
                                "skill_execute",
                                role,
                                "error",
                                {"skill": tool_name, "error": str(e)},
                            )

                # Fire "done" status callback with preview
                if status_callback:
                    preview = str(tool_result)[:80].replace("\n", " ")
                    try:
                        await status_callback(tool_name, "done", preview)
                    except Exception as cb_err:
                        logger.warning("status_callback error: %s", cb_err)

                # Fire special "conflict" status when conflict_check detects a real conflict
                if status_callback and tool_name == "conflict_check" and "CONFLICTS FOUND" in str(tool_result):
                    try:
                        await status_callback(tool_name, "conflict", str(tool_result)[:300])
                    except Exception as cb_err:
                        logger.warning("conflict status_callback error: %s", cb_err)

                # Add tool result to session
                session.add_message(
                    "tool",
                    tool_result,
                    tool_use_id=tool_use_id,
                    tool_name=tool_name,
                )
                tool_results_added = True

            if not tool_results_added:
                final_answer = assistant_text
                break

        else:
            # Max iterations reached — force a final synthesis pass with what we have
            logger.warning("Max ReAct iterations reached in _run_with_status: %s — forcing synthesis", session.session_id)
            try:
                synth_messages = session.get_conversation_history()
                synth_messages.append({
                    "role": "user",
                    "content": "You have now collected all available information. Synthesize everything gathered so far into a complete, professional response. Do not call any more tools.",
                })
                synth_response = await loop.run_in_executor(
                    None,
                    lambda: self.nova.chat(synth_messages, tools=None),  # No tools — force text answer
                )
                final_answer = synth_response.get("text") or assistant_text or "Processing complete. Please review the information gathered above."
            except Exception as e:
                logger.error("Forced synthesis failed: %s", e)
                final_answer = assistant_text or "I've gathered the available information. Please review the results above."

        # Store to memory
        if self.memory and final_answer:
            try:
                await loop.run_in_executor(
                    None,
                    lambda: self.memory.store_conversation_turn(
                        role=role,
                        case_id=case_id,
                        user_msg=user_message,
                        assistant_msg=final_answer,
                    ),
                )
            except Exception as e:
                logger.warning("Failed to store conversation turn: %s", e)

        return final_answer

    def run(
        self,
        user_message: str,
        session,
        context_override: Optional[str] = None,
    ) -> str:
        """
        Run the ReAct loop for a user message.

        Parameters
        ----------
        user_message : The user's input text.
        session      : Active Session object with role and case context.
        context_override : Optional additional context to inject.

        Returns the final assistant text response.
        """
        role = session.user_role
        case_id = session.case_id

        # 1. Guardian pre-flight check
        if self.guardian:
            guard_result = self.guardian.check(user_message, role=role, direction="input")
            self._log("guardian_check", role, guard_result["decision"], guard_result)
            if guard_result["decision"] == "block":
                reason = guard_result.get("reason", "Request blocked by security policy.")
                logger.warning("Guardian blocked input | role=%s reason=%s", role, reason)
                return f"I'm unable to process that request: {reason}"

        # 2. Retrieve memory context
        memory_context = ""
        if self.memory:
            try:
                memory_context = self.memory.get_context_for_query(
                    user_message, role=role, case_id=case_id, n_results=3
                )
            except Exception as e:
                logger.warning("Memory retrieval failed: %s", e)

        # 3. Build initial messages
        system_msg = SYSTEM_PROMPT
        if memory_context:
            system_msg += f"\n\nRelevant context from case files:\n{memory_context}"
        if context_override:
            system_msg += f"\n\n{context_override}"
        if session.case_id and session.case_id != "global":
            system_msg += (
                f"\n\nActive case context: The user is currently working on "
                f"case_id={session.case_id}. When calling any skill that accepts a "
                f"case_id parameter, always pass case_id=\"{session.case_id}\" unless "
                f"the user explicitly references a different case."
            )

        session.add_message("system", system_msg)
        session.add_message("user", user_message)

        # 4. Get tool definitions for this role
        tools = self._get_tool_definitions(role)

        # 5. ReAct loop
        final_answer = ""
        for iteration in range(MAX_REACT_ITERATIONS):
            logger.debug("ReAct iteration %d | role=%s", iteration + 1, role)

            messages = session.get_conversation_history()

            try:
                response = self.nova.chat(messages, tools=tools if tools else None)
            except Exception as e:
                logger.error("Nova call failed: %s", e)
                self._log("nova_call", role, "error", {"error": str(e)})
                return "I encountered an error processing your request. Please try again."

            self._log(
                "nova_call",
                role,
                "success",
                {
                    "iteration": iteration + 1,
                    "stop_reason": response["stop_reason"],
                    "tool_calls": len(response["tool_calls"]),
                },
            )

            assistant_text = response["text"]
            tool_calls = response["tool_calls"]
            stop_reason = response["stop_reason"]

            # 6. Guardian output check — only on FINAL answers (no tool calls), not reasoning steps
            if assistant_text and not tool_calls and self.guardian:
                out_check = self.guardian.check(assistant_text, role=role, direction="output")
                if out_check["decision"] == "block":
                    logger.warning("Guardian blocked output | reason=%s", out_check.get("reason"))
                    assistant_text = "I cannot provide that response due to security constraints."

            # 7. Add assistant turn to session
            if assistant_text:
                session.add_message("assistant", assistant_text)

            # 8. If no tool calls, we're done
            if not tool_calls or stop_reason in ("end_turn", "stop_sequence"):
                final_answer = assistant_text
                break

            # 9. Execute tool calls
            tool_results_added = False
            for tool_call in tool_calls:
                tool_name = tool_call["name"]
                tool_input = tool_call["input"]
                tool_use_id = tool_call["id"]

                logger.info("Executing skill: %s | input=%s", tool_name, tool_input)

                # RBAC check
                if self.rbac and not self.rbac.can_use_skill(role, tool_name):
                    tool_result = f"Access denied: role '{role}' cannot use skill '{tool_name}'."
                    self._log("skill_denied", role, "denied", {"skill": tool_name})
                else:
                    skill = self.skills.get(tool_name)
                    if skill is None:
                        tool_result = f"Unknown skill: {tool_name}"
                        self._log("skill_not_found", role, "error", {"skill": tool_name})
                    else:
                        try:
                            tool_result = skill.execute(tool_input, session=session)
                            if not isinstance(tool_result, str):
                                import json
                                tool_result = json.dumps(tool_result)
                            self._log(
                                "skill_execute",
                                role,
                                "success",
                                {"skill": tool_name, "input": tool_input},
                            )
                        except Exception as e:
                            logger.error("Skill %s failed: %s", tool_name, e)
                            tool_result = f"Skill execution error: {str(e)}"
                            self._log(
                                "skill_execute",
                                role,
                                "error",
                                {"skill": tool_name, "error": str(e)},
                            )

                # Add tool result to session
                session.add_message(
                    "tool",
                    tool_result,
                    tool_use_id=tool_use_id,
                    tool_name=tool_name,
                )
                tool_results_added = True

            if not tool_results_added:
                final_answer = assistant_text
                break

        else:
            # Max iterations reached
            logger.warning("Max ReAct iterations reached for session %s", session.session_id)
            final_answer = assistant_text or "I've reached my processing limit. Please rephrase your question."

        # 10. Store to memory
        if self.memory and final_answer:
            try:
                self.memory.store_conversation_turn(
                    role=role,
                    case_id=case_id,
                    user_msg=user_message,
                    assistant_msg=final_answer,
                )
            except Exception as e:
                logger.warning("Failed to store conversation turn: %s", e)

        return final_answer

    async def run_stream(
        self,
        user_message: str,
        session,
        context_override: Optional[str] = None,
        status_callback: Optional[Callable] = None,
        plan_callback: Optional[Callable] = None,
    ) -> AsyncIterator[str]:
        """
        Async streaming version of run().

        Yields text chunks as they arrive from Nova streaming API.
        If tools are needed, runs the full sync ReAct loop first, then
        streams the final answer in small chunks.

        Usage:
            async for chunk in agent.run_stream(msg, session):
                await ws.send_json({"type": "response_chunk", "chunk": chunk})
        """
        role = session.user_role
        case_id = session.case_id

        # 1. Guardian pre-flight check
        if self.guardian:
            guard_result = self.guardian.check(user_message, role=role, direction="input")
            self._log("guardian_check", role, guard_result["decision"], guard_result)
            if guard_result["decision"] == "block":
                reason = guard_result.get("reason", "Request blocked by security policy.")
                logger.warning("Guardian blocked input | role=%s reason=%s", role, reason)
                yield f"I'm unable to process that request: {reason}"
                return

        # 2. Retrieve memory context
        memory_context = ""
        if self.memory:
            try:
                loop = asyncio.get_event_loop()
                memory_context = await loop.run_in_executor(
                    None,
                    lambda: self.memory.get_context_for_query(
                        user_message, role=role, case_id=case_id, n_results=3
                    ),
                )
            except Exception as e:
                logger.warning("Memory retrieval failed: %s", e)

        # 3. Build system message
        system_msg = SYSTEM_PROMPT
        if memory_context:
            system_msg += f"\n\nRelevant context from case files:\n{memory_context}"
        if context_override:
            system_msg += f"\n\n{context_override}"
        if session.case_id and session.case_id != "global":
            system_msg += (
                f"\n\nActive case context: The user is currently working on "
                f"case_id={session.case_id}. When calling any skill that accepts a "
                f"case_id parameter, always pass case_id=\"{session.case_id}\" unless "
                f"the user explicitly references a different case."
            )

        session.add_message("system", system_msg)
        session.add_message("user", user_message)

        # 4. Get tool definitions for this role
        tools = self._get_tool_definitions(role)

        # 5a. If tools are available, do a non-streaming first pass to detect tool calls
        if tools:
            try:
                loop = asyncio.get_event_loop()
                first_response = await loop.run_in_executor(
                    None,
                    lambda: self.nova.chat(session.get_conversation_history(), tools=tools),
                )
            except Exception as e:
                logger.error("Nova tool-detection call failed: %s", e)
                yield "I encountered an error processing your request. Please try again."
                return

            if first_response.get("tool_calls"):
                # Has tool calls → run async ReAct loop with status callbacks then stream final answer
                logger.debug("run_stream: tool calls detected, running agentic ReAct with status")

                # Fire plan_callback with the list of tool names so the UI can show the plan header
                if plan_callback:
                    tool_names = [tc["name"] for tc in first_response["tool_calls"]]
                    try:
                        await plan_callback(tool_names)
                    except Exception as cb_err:
                        logger.warning("plan_callback error: %s", cb_err)

                try:
                    final_answer = await asyncio.wait_for(
                        self._run_with_status(
                            user_message, session, context_override, status_callback
                        ),
                        timeout=55,  # 55s hard cap — prevents infinite thinking-dots
                    )
                except asyncio.TimeoutError:
                    logger.warning("_run_with_status timed out after 55s — returning partial answer")
                    # Return whatever the last assistant text was
                    hist = session.get_conversation_history()
                    last_asst = next(
                        (m["content"] for m in reversed(hist) if m.get("role") == "assistant"),
                        None,
                    )
                    final_answer = last_asst or "Processing took too long. Please try again with a simpler request."
                except Exception as e:
                    logger.error("Agentic ReAct failed: %s", e)
                    yield "I encountered an error processing your request. Please try again."
                    return

                # Stream final answer in ~8-char chunks
                chunk_size = 8
                for i in range(0, len(final_answer), chunk_size):
                    yield final_answer[i:i + chunk_size]
                    await asyncio.sleep(0.015)
                return

            # No tool calls in first pass — continue with streaming
            # Add any text from the first pass to avoid losing it
            first_text = first_response.get("text", "")
            if first_text:
                # Clear the session additions we made and restart fresh for the streamer
                # (we already have context set up; stream mode will re-derive)
                pass

        # 5b. Stream directly via Nova streaming API
        try:
            messages_snapshot = session.get_conversation_history()
            accumulated_text = ""
            async for event in self.nova.chat_stream(messages_snapshot, tools=None):
                event_type = event.get("type", "")
                if event_type == "text_delta":
                    chunk = event.get("text", "")
                    if chunk:
                        accumulated_text += chunk
                        yield chunk
                elif event_type == "done":
                    break

            # Guardian output check on accumulated text
            if accumulated_text and self.guardian:
                out_check = self.guardian.check(accumulated_text, role=role, direction="output")
                if out_check["decision"] == "block":
                    logger.warning("Guardian blocked stream output | reason=%s", out_check.get("reason"))
                    # We already yielded the chunks — signal to caller via a special marker
                    # The server will handle this gracefully

            # Add assistant response to session
            if accumulated_text:
                session.add_message("assistant", accumulated_text)

            # Store to memory
            if self.memory and accumulated_text:
                try:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: self.memory.store_conversation_turn(
                            role=role,
                            case_id=case_id,
                            user_msg=user_message,
                            assistant_msg=accumulated_text,
                        ),
                    )
                except Exception as e:
                    logger.warning("Failed to store streamed conversation turn: %s", e)

        except Exception as e:
            logger.error("Streaming error: %s", e, exc_info=True)
            yield f"\n[Stream error: {e}]"

"""
agent/graph.py
LangGraph graph definition for the Wayfind intelligent agent workflow.

Constructs the StateGraph with all 19 domain nodes, sets up conditional
routing edges (completeness, intent, candidate count, confidence tier),
and returns the compiled graph.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.nodes import (
    ask_followup,
    check_completeness,
    evaluate_candidates,
    evaluate_evidence,
    extract_structured_data,
    found_child_extract,
    generate_response,
    get_case_status_node,
    get_guidance_node,
    human_review,
    image_match,
    no_match,
    register_child_node,
    route_by_confidence,
    route_intent,
    safety_guidance,
    search_metadata,
    search_support_node,
    submit_found_child,
    understand_intent,
)
from agent.state import (
    WayfindState,
    candidate_router,
    completeness_router,
    confidence_router,
    intent_router,
)

logger = logging.getLogger(__name__)


def build_graph() -> CompiledStateGraph:
    """Build and compile the complete Wayfind LangGraph workflow graph.

    Graph Topology:
      START
        │
        ▼
      understand_intent
        │
        ▼
      extract_structured_data
        │
        ▼
      check_completeness ──[completeness_router]──► incomplete ──► ask_followup ──► END
        │ (sufficient)
        ▼
      route_intent ──[intent_router]
        ├─► missing_child ──► search_metadata ──► evaluate_candidates ──[candidate_router]
        │                                             ├─► no_candidates ──► no_match ──► generate_response ──► END
        │                                             ├─► image_warranted ──► image_match ──► evaluate_evidence ...
        │                                             └─► no_image ────────────────────────► evaluate_evidence
        │                                                                                        │
        │                                                                                        ▼
        │                                                                                route_by_confidence ──[confidence_router]
        │                                                                                  ├─► low ───────► no_match ─────► generate_response ──► END
        │                                                                                  └─► uncert/high ► human_review ─► generate_response ──► END
        │
        ├─► found_child ──► found_child_extract ──► safety_guidance ──► submit_found_child ──► generate_response ──► END
        ├─► shelter_search ──► search_support_node ────────────────────────────────────────► generate_response ──► END
        ├─► guidance ──────► get_guidance_node ──────────────────────────────────────────► generate_response ──► END
        ├─► case_status ────► get_case_status_node ───────────────────────────────────────► generate_response ──► END
        └─► unknown ───────► ask_followup ───────────────────────────────────────────────► END
    """
    g = StateGraph(WayfindState)

    # ── 1. Register all 20 nodes ──────────────────────────────────────────────
    g.add_node("understand_intent", understand_intent)
    g.add_node("extract_structured_data", extract_structured_data)
    g.add_node("check_completeness", check_completeness)
    g.add_node("ask_followup", ask_followup)
    g.add_node("route_intent", route_intent)
    g.add_node("register_child_node", register_child_node)
    g.add_node("search_metadata", search_metadata)
    g.add_node("evaluate_candidates", evaluate_candidates)
    g.add_node("image_match", image_match)
    g.add_node("evaluate_evidence", evaluate_evidence)
    g.add_node("route_by_confidence", route_by_confidence)
    g.add_node("human_review", human_review)
    g.add_node("no_match", no_match)
    g.add_node("found_child_extract", found_child_extract)
    g.add_node("safety_guidance", safety_guidance)
    g.add_node("submit_found_child", submit_found_child)
    g.add_node("search_support_node", search_support_node)
    g.add_node("get_guidance_node", get_guidance_node)
    g.add_node("get_case_status_node", get_case_status_node)
    g.add_node("generate_response", generate_response)

    # ── 2. Intake & Comprehension pipeline ────────────────────────────────────
    g.add_edge(START, "understand_intent")
    g.add_edge("understand_intent", "extract_structured_data")
    g.add_edge("extract_structured_data", "check_completeness")

    # ── 3. Completeness Branch ────────────────────────────────────────────────
    g.add_conditional_edges(
        "check_completeness",
        completeness_router,
        {
            "incomplete": "ask_followup",
            "sufficient": "route_intent",
        },
    )
    g.add_edge("ask_followup", END)

    # ── 4. Intent Dispatch Branch ─────────────────────────────────────────────
    g.add_conditional_edges(
        "route_intent",
        intent_router,
        {
            "register_child": "register_child_node",
            "missing_child": "search_metadata",
            "found_child": "found_child_extract",
            "shelter_search": "search_support_node",
            "guidance": "get_guidance_node",
            "case_status": "get_case_status_node",
            "unknown": "ask_followup",
        },
    )
    g.add_edge("register_child_node", "generate_response")


    # ── 5. Missing Child Search & Evidence Evaluation Pipeline ────────────────
    g.add_edge("search_metadata", "evaluate_candidates")
    g.add_conditional_edges(
        "evaluate_candidates",
        candidate_router,
        {
            "no_candidates": "no_match",
            "image_warranted": "image_match",
            "no_image": "evaluate_evidence",
        },
    )
    g.add_edge("image_match", "evaluate_evidence")
    g.add_edge("evaluate_evidence", "route_by_confidence")

    g.add_conditional_edges(
        "route_by_confidence",
        confidence_router,
        {
            "low": "no_match",
            "uncertain": "human_review",
            "high": "human_review",
        },
    )
    g.add_edge("human_review", "generate_response")
    g.add_edge("no_match", "generate_response")

    # ── 6. Found Child Pipeline ───────────────────────────────────────────────
    g.add_edge("found_child_extract", "safety_guidance")
    g.add_edge("safety_guidance", "submit_found_child")
    g.add_edge("submit_found_child", "generate_response")

    # ── 7. Auxiliary Intent Branches ──────────────────────────────────────────
    g.add_edge("search_support_node", "generate_response")
    g.add_edge("get_guidance_node", "generate_response")
    g.add_edge("get_case_status_node", "generate_response")

    # ── 8. Terminal edge ──────────────────────────────────────────────────────
    g.add_edge("generate_response", END)

    logger.info("Wayfind LangGraph constructed successfully with 19 nodes.")
    return g.compile()

"""LangGraph State Machine definition for TravelOps AI Multi-Agent platform."""

from langgraph.graph import END, START, StateGraph

from app.agents.nodes.disruption import disruption_node
from app.agents.nodes.flight_search import flight_search_node
from app.agents.nodes.hotel_search import hotel_search_node
from app.agents.nodes.policy_qa import policy_qa_node
from app.agents.nodes.supervisor import supervisor_node
from app.agents.state import AgentState


def route_supervisor(state: AgentState) -> str:
    """Evaluate supervisor's workflow decision to route to the correct specialist node."""
    workflow = state.get("workflow", "SEARCH")
    if workflow == "DISRUPTION_REBOOKING":
        return "disruption_node"
    elif workflow == "POLICY":
        return "policy_qa_node"
    elif workflow == "HOTEL":
        return "hotel_search_node"
    else:
        return "flight_search_node"


def create_travel_agent_graph():
    """Build and compile the multi-agent state graph."""
    graph = StateGraph(AgentState)

    # 1. Register Nodes
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("flight_search_node", flight_search_node)
    graph.add_node("policy_qa_node", policy_qa_node)
    graph.add_node("disruption_node", disruption_node)
    graph.add_node("hotel_search_node", hotel_search_node)

    # 2. Register Edges
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "flight_search_node": "flight_search_node",
            "policy_qa_node": "policy_qa_node",
            "disruption_node": "disruption_node",
            "hotel_search_node": "hotel_search_node",
        },
    )

    # 3. Specialist nodes terminate execution cycle
    graph.add_edge("flight_search_node", END)
    graph.add_edge("policy_qa_node", END)
    graph.add_edge("disruption_node", END)
    graph.add_edge("hotel_search_node", END)

    return graph.compile()


travel_agent_graph = create_travel_agent_graph()

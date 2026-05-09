"""Courses swarm — 5 agents for educational content production."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agency_swarm import Agency

INSTRUCTIONS = Path(__file__).parent / "instructions"


def create_agency(load_threads_callback=None) -> "Agency":
    from agency_swarm import Agency
    from agency_swarm.tools import Handoff, SendMessage, WebSearchTool

    from orchestrator.tools import SwitchProvider, SwitchSwarm
    from swarms._common.agent_factory import make_agent
    from swarms._common.file_ops import ReadFile, WriteFile, EditFile, ListDir

    orch = make_agent(
        "Orchestrator",
        "Routes course-development work to the right specialist.",
        INSTRUCTIONS,
        tools=[SwitchProvider, SwitchSwarm],
    )
    designer = make_agent(
        "CourseDesigner",
        "Plans the course: learning objectives, prerequisites, sequence, assessments.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, ListDir, WebSearchTool],
        reasoning="high",
    )
    lesson_writer = make_agent(
        "LessonWriter",
        "Writes individual lessons: explanations, worked examples, key takeaways.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir, WebSearchTool],
    )
    exercise_writer = make_agent(
        "ExerciseWriter",
        "Creates exercises and quizzes with model solutions and answer keys.",
        INSTRUCTIONS,
        tools=[ReadFile, WriteFile, EditFile, ListDir],
    )
    editor = make_agent(
        "Editor",
        "Reviews lessons and exercises for pedagogical clarity and accuracy.",
        INSTRUCTIONS,
        tools=[ReadFile, EditFile, ListDir],
        reasoning="high",
    )

    agents = [orch, designer, lesson_writer, exercise_writer, editor]
    send_message_flows = [(orch, a, SendMessage) for a in agents if a is not orch]
    handoff_flows = [(a > b, Handoff) for a in agents for b in agents if a is not b]

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="Courses",
        shared_instructions=str(Path(__file__).parent / "shared_instructions.md"),
        load_threads_callback=load_threads_callback,
    )

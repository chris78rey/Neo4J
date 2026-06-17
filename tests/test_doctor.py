from neo4j_graphrag.cli import build_parser


def test_doctor_command_registered():
    parser = build_parser()
    subcommands = parser._subparsers._group_actions[0].choices
    assert "doctor" in subcommands

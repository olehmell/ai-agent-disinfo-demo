"""Content-analysis demo: one use case, three architectures.

The three analytical contours are implemented once in ``contours.py`` and reused by
three different orchestrations:

- ``workflow_graph``  deterministic state graph
- ``single_agent``    one model-directed ReAct agent
- ``multi_agent``     supervisor + specialist sub-agents

The point of the demo is to compare architectures, not capability.
"""

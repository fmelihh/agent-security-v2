"""The tool executor: the boundary the agent talks to over HTTP.

Only this package touches customer data. The agent process gets typed results with
PII replaced by handles, and every write goes out through ``egress``.
"""

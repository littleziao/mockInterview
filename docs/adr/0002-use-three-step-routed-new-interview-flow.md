# Use a three-step routed new interview flow

The new interview flow uses three independent routed pages: resume upload, resume analysis and configuration, and interview start. This replaces the earlier single-page flow because each step has a distinct user intent and state boundary: resume and target role feed analysis, analysis and configuration feed session creation, and the interview page should only focus on the current question and answer. The pages share one new interview context so browser navigation and step transitions do not silently lose state.

## Consequences

Changing resume or target role after analysis must explicitly invalidate later analysis and session state. Once an interview session has started, configuration is read-only unless the user abandons the current session and starts again.

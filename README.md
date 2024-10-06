# Open WebUI ReAct agent

If you're not using OpenAI/Ollama/Langfuse just leave their respective valves empty.

You need to add this in the Functions tab in OpenWebUI. It won't affect anything unless you've got any Tools enabled. Apart from streaming/citations related fuff, the implementation is quite straightforward, relying on LangGraph's `create_react_agent`.

# Open WebUI ReAct agent

## `react_agent_langfuse.py`

If you're not using OpenAI/Ollama/Langfuse just leave their respective valves empty.

You need to add this in the Functions tab in OpenWebUI. It won't affect anything unless you've got any Tools enabled. Apart from streaming/citations related fuff, the implementation is quite straightforward, relying on LangGraph's `create_react_agent`.

## `langfuse_capture_rating.py`

Modifies OWUI's existing like/dislike buttons to forward the rating to Langfuse. It still creates a dialogue for more information, which doesn't really do anything.

## `langfuse_like_action.py` and `langfuse_dislike_action.py`

Create a new button for like and dislike, to be used with `ENABLE_MESSAGE_RATING=false`. More configurable than `langfuse_capture_rating.py` but the theme is a bit off.

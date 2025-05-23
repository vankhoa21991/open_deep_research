from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import uuid
from src.open_deep_research.graph import graph
from langgraph.types import Command

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def chat_ui():
    return """
    <!DOCTYPE html>
    <html lang='en'>
    <head>
        <meta charset='UTF-8'>
        <title>Open Deep Research Chat</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f4f4f4; }
            #chat { width: 400px; margin: 40px auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 8px #ccc; padding: 20px; }
            #messages { height: 300px; overflow-y: auto; border: 1px solid #eee; padding: 10px; margin-bottom: 10px; background: #fafafa; }
            .msg { margin: 8px 0; }
            .user { color: #0074d9; }
            .ai { color: #2ecc40; }
            #input { width: 80%; padding: 8px; }
            #send { width: 18%; padding: 8px; }
        </style>
    </head>
    <body>
        <div id='chat'>
            <h2>Open Deep Research Chat</h2>
            <div id='messages'></div>
            <input id='input' type='text' placeholder='Type your message...' autofocus />
            <button id='send'>Send</button>
        </div>
        <script>
            let thread_id = Math.random().toString(36).substring(2, 10);
            let state = null;
            let started = false;
            const messagesDiv = document.getElementById('messages');
            const input = document.getElementById('input');
            const sendBtn = document.getElementById('send');

            function appendMessage(text, who) {
                const div = document.createElement('div');
                div.className = 'msg ' + who;
                div.textContent = (who === 'user' ? 'You: ' : 'AI: ') + text;
                messagesDiv.appendChild(div);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }

            async function sendMessage() {
                const userMsg = input.value.trim();
                if (!userMsg) return;
                appendMessage(userMsg, 'user');
                input.value = '';
                let url;
                if (!started) {
                    url = `/chat_initiate?thread_id=${thread_id}&message=${encodeURIComponent(userMsg)}`;
                    started = true;
                } else {
                    url = `/chat-continue?thread_id=${thread_id}&message=${encodeURIComponent(userMsg)}`;
                }
                appendMessage('...', 'ai');
                const resp = await fetch(url);
                const data = await resp.json();
                messagesDiv.removeChild(messagesDiv.lastChild);
                appendMessage(data.AIMessage, 'ai');
                state = data.state;
            }

            sendBtn.onclick = sendMessage;
            input.onkeydown = function(e) { if (e.key === 'Enter') sendMessage(); };
        </script>
    </body>
    </html>
    """

@app.get("/chat_initiate")
async def chat_initiate(thread_id: str, message: str):
    thread_config = {"configurable": {"thread_id": thread_id}}
    # Start a new report with the user's message as the topic
    # state = await graph.ainvoke({"topic": message}, config=thread_config)

    async for event in graph.astream({"topic":message,}, thread_config, stream_mode="updates"):
        if '__interrupt__' in event:
            interrupt_value = event['__interrupt__'][0].value
            break

    return {
        "AIMessage": interrupt_value,
        # "state": state
    }

@app.get("/chat-continue")
async def chat_continue(thread_id: str, message: str):
    thread_config = {"configurable": {"thread_id": thread_id}}
    # Continue the report with user feedback or a new command
    async for event in graph.astream(Command(resume=message), thread_config, stream_mode="updates"):
        if '__interrupt__' in event:
            interrupt_value = event['__interrupt__'][0].value
            break

    async for event in graph.astream(Command(resume=True), thread_config, stream_mode="updates"):
        print(event)
        print('/n')

    final_state = graph.get_state(thread_config)
    report = final_state.values.get('final_report')



    return {
        "AIMessage": report,
        # "state": state,
        "thread_id": thread_id
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

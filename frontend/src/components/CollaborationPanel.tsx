import React, { useState, useEffect, useRef } from 'react';
import useCADStore from '../store/cadStore';

export const CollaborationPanel: React.FC = () => {
  const { collaboration, joinSession, leaveSession, sendChatMessage } = useCADStore();
  const [sessionInput, setSessionInput] = useState('');
  const [chatInput, setChatInput] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [collaboration.chat]);

  const handleJoin = () => {
    const id = sessionInput.trim() || Math.random().toString(36).slice(2, 10);
    joinSession(id);
    setSessionInput('');
  };

  const handleSendChat = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    sendChatMessage(chatInput.trim());
    setChatInput('');
  };

  const copySessionId = () => {
    if (collaboration.sessionId) {
      navigator.clipboard.writeText(collaboration.sessionId);
    }
  };

  const participants = Object.values(collaboration.participants);

  return (
    <div className="panel flex flex-col gap-3 p-4 h-full">
      <h2 className="text-lg font-semibold text-sky-400">Collaboration</h2>

      {/* Connection status */}
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${collaboration.isConnected ? 'bg-green-500' : 'bg-zinc-600'}`} />
        <span className="text-xs text-zinc-400">
          {collaboration.isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      {/* Session management */}
      {!collaboration.sessionId ? (
        <div className="flex flex-col gap-2">
          <label className="label">Session ID</label>
          <input
            className="input text-sm"
            placeholder="Enter or leave blank for new session..."
            value={sessionInput}
            onChange={(e) => setSessionInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleJoin()}
          />
          <button onClick={handleJoin} className="btn-primary justify-center">
            Join / Create Session
          </button>
        </div>
      ) : (
        <div className="bg-zinc-800 rounded p-3 flex items-center justify-between gap-2">
          <div>
            <p className="text-xs text-zinc-500">Session ID</p>
            <p className="text-sm font-mono text-sky-400">{collaboration.sessionId}</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={copySessionId}
              title="Copy session ID"
              className="btn-secondary text-xs px-2 py-1"
            >
              Copy
            </button>
            <button
              onClick={leaveSession}
              className="px-2 py-1 rounded text-xs bg-red-900/50 hover:bg-red-800 text-red-300 transition-colors"
            >
              Leave
            </button>
          </div>
        </div>
      )}

      {/* Participants */}
      {participants.length > 0 && (
        <div>
          <label className="label">Participants ({participants.length})</label>
          <div className="flex flex-col gap-1.5">
            {participants.map((p) => (
              <div key={p.participant_id} className="flex items-center gap-2 text-sm">
                <div
                  className="w-3 h-3 rounded-full shrink-0"
                  style={{ backgroundColor: p.color }}
                />
                <span className="text-zinc-300 truncate">{p.name}</span>
                {p.cursor_position && (
                  <span className="text-xs text-zinc-600 font-mono ml-auto">
                    ({p.cursor_position.x.toFixed(0)}, {p.cursor_position.y.toFixed(0)}, {p.cursor_position.z.toFixed(0)})
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Chat */}
      {collaboration.sessionId && (
        <div className="flex flex-col gap-2 flex-1 min-h-0">
          <label className="label">Chat</label>
          <div className="flex-1 bg-zinc-800 rounded p-2 overflow-y-auto min-h-[100px] max-h-48">
            {collaboration.chat.length === 0 ? (
              <p className="text-xs text-zinc-600 text-center mt-4">No messages yet</p>
            ) : (
              collaboration.chat.map((msg, i) => (
                <div key={i} className="mb-2">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: msg.color }} />
                    <span className="text-xs font-medium" style={{ color: msg.color }}>
                      {msg.participant_name}
                    </span>
                    <span className="text-xs text-zinc-600">
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-sm text-zinc-300 pl-3.5">{msg.message}</p>
                </div>
              ))
            )}
            <div ref={chatEndRef} />
          </div>
          <form onSubmit={handleSendChat} className="flex gap-2">
            <input
              className="input flex-1 text-sm"
              placeholder="Type a message..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
            />
            <button type="submit" className="btn-primary px-3">
              Send
            </button>
          </form>
        </div>
      )}
    </div>
  );
};

export default CollaborationPanel;

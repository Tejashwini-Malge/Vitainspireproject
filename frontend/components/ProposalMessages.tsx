'use client';

import { useEffect, useState, useRef } from 'react';
import { api } from '@/lib/api';

interface Message {
  id: string;
  proposal_id: string;
  sender_id: string;
  sender_type: string;
  content: string;
  created_at: string;
  read_at: string | null;
}

interface Timeline {
  proposal_id: string;
  last_activity_at: string;
  reply_deadline: string | null;
  waiting_on: string | null;
  days_since_activity: number;
  is_overdue: boolean;
}

interface ProposalMessagesProps {
  proposalId: string;
  currentUserType: 'NGO' | 'CSR';
}

export default function ProposalMessages({ proposalId, currentUserType }: ProposalMessagesProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [proposalId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadData = async () => {
    try {
      const [msgs, tl] = await Promise.all([
        api<Message[]>(`/proposals/${proposalId}/messages`),
        api<Timeline>(`/proposals/${proposalId}/timeline`),
      ]);
      setMessages(msgs || []);
      setTimeline(tl);
    } catch (err) {
      setError('Failed to load messages');
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim()) return;

    setSending(true);
    try {
      const msg = await api<Message>(`/proposals/${proposalId}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content: newMessage }),
      });
      setMessages([...messages, msg]);
      setNewMessage('');
      setTimeline((prev) =>
        prev
          ? {
              ...prev,
              last_activity_at: msg.created_at,
              waiting_on: currentUserType === 'NGO' ? 'CSR' : 'NGO',
              days_since_activity: 0,
            }
          : null
      );
    } catch (err) {
      setError('Failed to send message');
    } finally {
      setSending(false);
    }
  };

  if (loading) return <div className="p-4 text-center text-gray-500">Loading messages...</div>;

  const otherParty = currentUserType === 'NGO' ? 'CSR' : 'NGO';
  const daysText =
    timeline?.days_since_activity === 0
      ? 'just now'
      : timeline?.days_since_activity === 1
      ? '1 day'
      : `${timeline?.days_since_activity} days`;

  return (
    <div className="space-y-6">
      {/* Timeline Bar */}
      {timeline && (
        <div className={`p-4 rounded-lg ${timeline.is_overdue ? 'bg-red-50' : 'bg-blue-50'}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-gray-900">
                ⏱️ Waiting for {timeline.waiting_on || otherParty}
              </p>
              <p className="text-sm text-gray-600">Last activity: {daysText} ago</p>
            </div>
            {timeline.is_overdue && (
              <span className="px-3 py-1 rounded-full bg-red-200 text-red-800 text-sm font-semibold">
                ⚠️ Overdue
              </span>
            )}
          </div>
        </div>
      )}

      {/* Messages Thread */}
      <div className="bg-white border rounded-lg h-96 overflow-y-auto space-y-4 p-4">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-gray-400 text-sm">
            No messages yet. Start the conversation!
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`p-3 rounded-lg ${
                msg.sender_type === currentUserType
                  ? 'bg-blue-100 ml-8 text-right'
                  : 'bg-gray-100 mr-8'
              }`}
            >
              <p className="text-xs font-semibold text-gray-600 mb-1">
                {msg.sender_type} • {new Date(msg.created_at).toLocaleString()}
              </p>
              <p className="text-gray-900 break-words">{msg.content}</p>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Message Input */}
      <div className="space-y-2">
        {error && <div className="text-red-600 text-sm">{error}</div>}
        <div className="flex gap-2">
          <textarea
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 p-3 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={3}
            disabled={sending}
          />
          <button
            onClick={handleSendMessage}
            disabled={!newMessage.trim() || sending}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 font-semibold h-fit"
          >
            {sending ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}

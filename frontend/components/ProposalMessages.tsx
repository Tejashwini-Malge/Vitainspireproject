'use client';

import { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, AlertTriangle, Send } from 'lucide-react';
import { api } from '@/lib/api';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

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

  if (loading) return <p className="p-4 text-center text-muted">Loading messages...</p>;

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
        <div
          className={`rounded-sm border p-4 ${
            timeline.is_overdue
              ? 'border-status-rejected/40 bg-status-rejected/10'
              : 'border-line bg-navy/5'
          }`}
        >
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 shrink-0 text-navy" />
              <div>
                <p className="font-semibold text-navy">
                  Waiting for {timeline.waiting_on || otherParty}
                </p>
                <p className="text-sm text-muted">Last activity: {daysText} ago</p>
              </div>
            </div>
            {timeline.is_overdue && (
              <Badge tone="rejected" className="gap-1">
                <AlertTriangle className="h-3 w-3" />
                Overdue
              </Badge>
            )}
          </div>
        </div>
      )}

      {/* Messages Thread */}
      <div className="h-96 space-y-3 overflow-y-auto rounded-sm border border-line bg-[#FFFDF7] p-4">
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            No messages yet. Start the conversation!
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {messages.map((msg) => {
              const mine = msg.sender_type === currentUserType;
              return (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                  className={`flex ${mine ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-sm px-4 py-2.5 ${
                      mine
                        ? 'border border-navy bg-navy text-paper'
                        : 'border border-line bg-paper text-ink'
                    }`}
                  >
                    <p className={`mb-1 font-mono text-xs uppercase tracking-wide ${mine ? 'text-paper/70' : 'text-muted'}`}>
                      {msg.sender_type} · {new Date(msg.created_at).toLocaleString()}
                    </p>
                    <p className="break-words">{msg.content}</p>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Message Input */}
      <div className="space-y-2">
        {error && <p className="text-sm text-status-rejected">{error}</p>}
        <div className="flex gap-2">
          <Textarea
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Type your message..."
            rows={3}
            disabled={sending}
            className="flex-1 resize-none"
          />
          <Button
            onClick={handleSendMessage}
            disabled={!newMessage.trim() || sending}
            variant="primary"
            size="md"
            className="h-fit self-end"
          >
            <Send className="h-4 w-4" />
            {sending ? 'Sending...' : 'Send'}
          </Button>
        </div>
      </div>
    </div>
  );
}

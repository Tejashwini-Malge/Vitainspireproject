'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import Link from 'next/link';
import { MessageSquare, CheckCircle2, PencilLine, Megaphone } from 'lucide-react';

interface Notification {
  id: string;
  recipient_user_id: string;
  proposal_id: string;
  notification_type: string;
  title: string;
  message: string;
  actor_user_id: string | null;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
}

interface NotificationCenterProps {
  onClose?: () => void;
}

export default function NotificationCenter({ onClose }: NotificationCenterProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadNotifications();
  }, []);

  const loadNotifications = async () => {
    try {
      const data = await api<Notification[]>('/notifications?limit=100');
      setNotifications(data || []);
    } catch (err) {
      setError('Failed to load notifications');
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAsRead = async (notificationId: string) => {
    try {
      await api(`/notifications/${notificationId}/read`, { method: 'PUT' });
      setNotifications(
        notifications.map((n) =>
          n.id === notificationId ? { ...n, is_read: true } : n
        )
      );
    } catch (err) {
      console.error('Failed to mark notification as read');
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await api('/notifications/mark-all-read', { method: 'PUT' });
      setNotifications(notifications.map((n) => ({ ...n, is_read: true })));
    } catch (err) {
      console.error('Failed to mark all as read');
    }
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'NEW_MESSAGE':
        return <MessageSquare className="h-4 w-4" />;
      case 'PROPOSAL_APPROVED':
        return <CheckCircle2 className="h-4 w-4" />;
      case 'CHANGES_REQUESTED':
        return <PencilLine className="h-4 w-4" />;
      default:
        return <Megaphone className="h-4 w-4" />;
    }
  };

  const getNotificationColor = (type: string) => {
    switch (type) {
      case 'NEW_MESSAGE':
        return 'text-navy bg-navy/5';
      case 'PROPOSAL_APPROVED':
        return 'text-status-approved bg-status-approved/10';
      case 'CHANGES_REQUESTED':
        return 'text-status-pending bg-status-pending/10';
      default:
        return 'text-muted bg-navy/5';
    }
  };

  if (loading) {
    return (
      <div className="w-full max-w-md rounded-sm border border-line bg-[#FFFDF7] p-4 text-center text-muted shadow-[0_8px_24px_rgba(29,43,79,0.12)]">
        Loading notifications...
      </div>
    );
  }

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="w-full max-w-md rounded-sm border border-line bg-[#FFFDF7] shadow-[0_8px_24px_rgba(29,43,79,0.12)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-line p-4">
        <div>
          <h2 className="font-display text-lg font-semibold text-navy">Notifications</h2>
          {unreadCount > 0 && (
            <p className="text-sm text-muted">{unreadCount} unread</p>
          )}
        </div>
        {unreadCount > 0 && (
          <button
            onClick={handleMarkAllAsRead}
            className="text-sm font-semibold text-teal hover:underline"
          >
            Mark all as read
          </button>
        )}
      </div>

      {/* Notifications List */}
      <div className="max-h-96 overflow-y-auto">
        {error && (
          <div className="p-4 text-sm text-status-rejected">{error}</div>
        )}

        {notifications.length === 0 ? (
          <div className="p-8 text-center text-muted">
            <p>No notifications yet</p>
          </div>
        ) : (
          notifications.map((notif) => (
            <Link
              key={notif.id}
              href={`/ngo/proposals/${notif.proposal_id}`}
              className={`block border-b border-line p-4 transition hover:bg-navy/5 ${
                !notif.is_read ? 'bg-teal/5' : ''
              }`}
              onClick={() => {
                if (!notif.is_read) {
                  handleMarkAsRead(notif.id);
                }
                onClose?.();
              }}
            >
              <div className="flex gap-3">
                {/* Icon */}
                <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${getNotificationColor(notif.notification_type)}`}>
                  {getNotificationIcon(notif.notification_type)}
                </span>

                {/* Content */}
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-1 font-semibold text-navy">
                    {notif.title}
                  </p>
                  <p className="line-clamp-2 text-sm text-muted">
                    {notif.message}
                  </p>
                  <p className="mt-1 font-mono text-xs text-muted">
                    {new Date(notif.created_at).toLocaleString()}
                  </p>
                </div>

                {/* Unread Badge */}
                {!notif.is_read && (
                  <div className="mt-2 h-2 w-2 shrink-0 rounded-full bg-teal" />
                )}
              </div>
            </Link>
          ))
        )}
      </div>

      {/* Footer */}
      {notifications.length > 0 && (
        <div className="border-t border-line p-4 text-center">
          <Link
            href="/notifications"
            className="text-sm font-semibold text-teal hover:underline"
          >
            View all notifications
          </Link>
        </div>
      )}
    </div>
  );
}

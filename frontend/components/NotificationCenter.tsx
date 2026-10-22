'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import Link from 'next/link';

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
        return '💬';
      case 'PROPOSAL_APPROVED':
        return '✅';
      case 'CHANGES_REQUESTED':
        return '✏️';
      default:
        return '📢';
    }
  };

  const getNotificationColor = (type: string) => {
    switch (type) {
      case 'NEW_MESSAGE':
        return 'border-blue-200 bg-blue-50';
      case 'PROPOSAL_APPROVED':
        return 'border-green-200 bg-green-50';
      case 'CHANGES_REQUESTED':
        return 'border-orange-200 bg-orange-50';
      default:
        return 'border-gray-200 bg-gray-50';
    }
  };

  if (loading) {
    return (
      <div className="p-4 text-center text-gray-500">
        Loading notifications...
      </div>
    );
  }

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="w-full max-w-md bg-white rounded-lg shadow-lg">
      {/* Header */}
      <div className="border-b p-4 flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Notifications</h2>
          {unreadCount > 0 && (
            <p className="text-sm text-gray-600">{unreadCount} unread</p>
          )}
        </div>
        {unreadCount > 0 && (
          <button
            onClick={handleMarkAllAsRead}
            className="text-sm text-blue-600 hover:text-blue-700 font-semibold"
          >
            Mark all as read
          </button>
        )}
      </div>

      {/* Notifications List */}
      <div className="max-h-96 overflow-y-auto">
        {error && (
          <div className="p-4 text-red-600 text-sm">{error}</div>
        )}

        {notifications.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <p>No notifications yet</p>
          </div>
        ) : (
          notifications.map((notif) => (
            <Link
              key={notif.id}
              href={`/ngo/proposals/${notif.proposal_id}`}
              className={`block border-b p-4 hover:bg-gray-50 transition ${
                !notif.is_read ? 'bg-blue-50' : ''
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
                <span className="text-xl flex-shrink-0">
                  {getNotificationIcon(notif.notification_type)}
                </span>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900 line-clamp-1">
                    {notif.title}
                  </p>
                  <p className="text-sm text-gray-600 line-clamp-2">
                    {notif.message}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {new Date(notif.created_at).toLocaleString()}
                  </p>
                </div>

                {/* Unread Badge */}
                {!notif.is_read && (
                  <div className="flex-shrink-0 w-2 h-2 rounded-full bg-blue-600 mt-2" />
                )}
              </div>
            </Link>
          ))
        )}
      </div>

      {/* Footer */}
      {notifications.length > 0 && (
        <div className="border-t p-4 text-center">
          <Link
            href="/notifications"
            className="text-blue-600 hover:text-blue-700 font-semibold text-sm"
          >
            View all notifications
          </Link>
        </div>
      )}
    </div>
  );
}

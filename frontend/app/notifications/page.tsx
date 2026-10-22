'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';

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

export default function NotificationsPage() {
  const router = useRouter();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<'all' | 'unread'>('all');

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }

    loadNotifications();
  }, [router, filter]);

  const loadNotifications = async () => {
    try {
      const data = await api<Notification[]>(
        `/notifications?${filter === 'unread' ? 'unread_only=true&' : ''}limit=200`
      );
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
        return 'border-l-4 border-l-blue-600 bg-blue-50';
      case 'PROPOSAL_APPROVED':
        return 'border-l-4 border-l-green-600 bg-green-50';
      case 'CHANGES_REQUESTED':
        return 'border-l-4 border-l-orange-600 bg-orange-50';
      default:
        return 'border-l-4 border-l-gray-600 bg-gray-50';
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-8">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold">Notifications</h1>
          <NotificationBell />
        </div>
        <div className="text-center py-12 text-gray-500">Loading...</div>
      </div>
    );
  }

  const unreadCount = notifications.filter((n) => !n.is_read).length;
  const filteredNotifications =
    filter === 'unread'
      ? notifications.filter((n) => !n.is_read)
      : notifications;

  return (
    <div className="max-w-4xl mx-auto p-8">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-bold">Notifications</h1>
          <p className="text-gray-600 mt-2">
            {unreadCount > 0
              ? `${unreadCount} unread notification${unreadCount !== 1 ? 's' : ''}`
              : 'All caught up!'}
          </p>
        </div>
        <div className="flex gap-4 items-center">
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllAsRead}
              className="text-sm text-blue-600 hover:text-blue-700 font-semibold"
            >
              Mark all as read
            </button>
          )}
          <NotificationBell />
        </div>
      </div>

      {/* Filter */}
      <div className="flex gap-4 mb-8">
        <button
          onClick={() => setFilter('all')}
          className={`px-4 py-2 rounded-lg font-semibold transition ${
            filter === 'all'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          All
        </button>
        <button
          onClick={() => setFilter('unread')}
          className={`px-4 py-2 rounded-lg font-semibold transition ${
            filter === 'unread'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          Unread
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-lg mb-8">
          {error}
        </div>
      )}

      {/* Notifications List */}
      {filteredNotifications.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-xl mb-2">
            {filter === 'unread' ? 'No unread notifications' : 'No notifications yet'}
          </p>
          <p>
            {filter === 'unread'
              ? 'Check back later for updates'
              : 'When you receive messages or updates, they will appear here'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredNotifications.map((notif) => (
            <Link
              key={notif.id}
              href={`/ngo/proposals/${notif.proposal_id}`}
              className={`block p-4 rounded-lg border transition hover:shadow-md ${getNotificationColor(
                notif.notification_type
              )} ${!notif.is_read ? 'shadow-sm' : ''}`}
              onClick={() => {
                if (!notif.is_read) {
                  handleMarkAsRead(notif.id);
                }
              }}
            >
              <div className="flex gap-4">
                {/* Icon */}
                <span className="text-3xl flex-shrink-0">
                  {getNotificationIcon(notif.notification_type)}
                </span>

                {/* Content */}
                <div className="flex-1">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-bold text-lg text-gray-900">
                        {notif.title}
                      </p>
                      <p className="text-gray-700 mt-1">{notif.message}</p>
                    </div>
                    {!notif.is_read && (
                      <div className="flex-shrink-0 ml-4">
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            handleMarkAsRead(notif.id);
                          }}
                          className="text-xs text-blue-600 hover:text-blue-700 font-semibold"
                        >
                          Mark as read
                        </button>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    {new Date(notif.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api';
import NotificationBell from '@/components/NotificationBell';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';

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

  const getNotificationTone = (type: string) => {
    switch (type) {
      case 'NEW_MESSAGE':
        return 'border-l-navy';
      case 'PROPOSAL_APPROVED':
        return 'border-l-status-approved';
      case 'CHANGES_REQUESTED':
        return 'border-l-status-pending';
      default:
        return 'border-l-line';
    }
  };

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight text-navy sm:text-3xl">Notifications</h1>
          <NotificationBell />
        </div>
        <p className="text-muted">Loading…</p>
      </div>
    );
  }

  const unreadCount = notifications.filter((n) => !n.is_read).length;
  const filteredNotifications =
    filter === 'unread'
      ? notifications.filter((n) => !n.is_read)
      : notifications;

  return (
    <div className="space-y-8">
      {/* Header */}
      <PageHeader
        eyebrow="Inbox"
        title="Notifications"
        description={unreadCount > 0 ? `${unreadCount} unread notification${unreadCount !== 1 ? 's' : ''}` : 'All caught up!'}
        action={
          <div className="flex items-center gap-4">
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllAsRead}
                className="text-sm font-semibold text-teal hover:underline"
              >
                Mark all as read
              </button>
            )}
            <NotificationBell />
          </div>
        }
      />

      {/* Filter */}
      <div className="flex gap-3">
        <Button variant={filter === 'all' ? 'primary' : 'secondary'} size="sm" onClick={() => setFilter('all')}>
          All
        </Button>
        <Button variant={filter === 'unread' ? 'primary' : 'secondary'} size="sm" onClick={() => setFilter('unread')}>
          Unread
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-sm border border-status-rejected/40 bg-status-rejected/5 p-4 text-sm text-status-rejected">
          {error}
        </div>
      )}

      {/* Notifications List */}
      {filteredNotifications.length === 0 ? (
        <EmptyState
          title={filter === 'unread' ? 'No unread notifications' : 'No notifications yet'}
          description={filter === 'unread' ? 'Check back later for updates.' : 'When you receive messages or updates, they will appear here.'}
        />
      ) : (
        <div className="space-y-4">
          {filteredNotifications.map((notif) => (
            <Link
              key={notif.id}
              href={`/ngo/proposals/${notif.proposal_id}`}
              onClick={() => {
                if (!notif.is_read) {
                  handleMarkAsRead(notif.id);
                }
              }}
              className="block"
            >
              <Card
                interactive
                className={`border-l-4 p-4 ${getNotificationTone(notif.notification_type)} ${!notif.is_read ? 'shadow-sm' : ''}`}
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
                        <p className="font-semibold text-lg text-navy">
                          {notif.title}
                        </p>
                        <p className="text-muted mt-1">{notif.message}</p>
                      </div>
                      {!notif.is_read && (
                        <div className="flex-shrink-0 ml-4">
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              handleMarkAsRead(notif.id);
                            }}
                            className="text-xs font-semibold text-teal hover:underline"
                          >
                            Mark as read
                          </button>
                        </div>
                      )}
                    </div>
                    <p className="text-xs text-muted mt-2">
                      {new Date(notif.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

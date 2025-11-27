'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Send, Users, AlertCircle, CheckCircle } from 'lucide-react';
import { toast } from "sonner";
import { formatDateTime } from '@/lib/utils';

export default function AdminBroadcastPage() {
  const [message, setMessage] = useState('');
  const [targetTier, setTargetTier] = useState('all');
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [sending, setSending] = useState(false);
  const [lastBroadcast, setLastBroadcast] = useState<{
    message: string;
    recipients: number;
    timestamp: string;
  } | null>(null);

  const handleSendBroadcast = async () => {
    if (!message.trim()) {
      toast.error('Please enter a message');
      return;
    }

    if (message.length > 1000) {
      toast.error('Message must be 1000 characters or less');
      return;
    }

    if (!confirm(`Are you sure you want to send this notification to ${verifiedOnly ? 'verified ' : ''}${targetTier === 'all' ? 'all users' : `${targetTier} tier users`}?`)) {
      return;
    }

    try {
      setSending(true);

      const response = await fetch('/api/admin/broadcast', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
        body: JSON.stringify({
          message: message.trim(),
          target_tier: targetTier === 'all' ? null : targetTier,
          target_verified_only: verifiedOnly,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        toast.success(data.message || 'Broadcast sent successfully');
        setLastBroadcast({
          message: message.trim(),
          recipients: data.recipients_count || 0,
          timestamp: new Date().toISOString(),
        });
        setMessage('');
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to send broadcast');
      }
    } catch (error) {
      console.error('Error sending broadcast:', error);
      toast.error('Failed to send broadcast');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Broadcast Notifications</h1>
        <p className="text-muted-foreground mt-1">
          Send notifications to all users or specific groups
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main broadcast form */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Compose Message</CardTitle>
              <CardDescription>
                Write your notification message below. It will be sent to all selected users.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="message">Message</Label>
                <Textarea
                  id="message"
                  placeholder="Enter your notification message..."
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={6}
                  className="resize-none"
                  maxLength={1000}
                />
                <p className="text-xs text-muted-foreground text-right">
                  {message.length}/1000 characters
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Target Subscription Tier</Label>
                  <Select value={targetTier} onValueChange={setTargetTier}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select tier" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Users</SelectItem>
                      <SelectItem value="free">Free Tier</SelectItem>
                      <SelectItem value="basic">Basic Tier</SelectItem>
                      <SelectItem value="premium">Premium Tier</SelectItem>
                      <SelectItem value="enterprise">Enterprise Tier</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Additional Filters</Label>
                  <div className="flex items-center space-x-2 h-10">
                    <Checkbox
                      id="verified"
                      checked={verifiedOnly}
                      onCheckedChange={(checked) => setVerifiedOnly(checked as boolean)}
                    />
                    <label
                      htmlFor="verified"
                      className="text-sm font-medium leading-none cursor-pointer"
                    >
                      Verified users only
                    </label>
                  </div>
                </div>
              </div>

              <Button
                onClick={handleSendBroadcast}
                disabled={sending || !message.trim()}
                className="w-full"
                size="lg"
              >
                {sending ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Sending...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4 mr-2" />
                    Send Broadcast
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Info card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">About Broadcasts</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-start gap-2 text-sm text-muted-foreground">
                <Users className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <p>
                  Broadcast notifications are sent to all users matching your selected criteria.
                </p>
              </div>
              <div className="flex items-start gap-2 text-sm text-muted-foreground">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-yellow-500" />
                <p>
                  Users will receive notifications in their dashboard and may receive email alerts
                  if enabled.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Last broadcast */}
          {lastBroadcast && (
            <Card className="border-green-200 bg-green-50">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg flex items-center gap-2 text-green-700">
                  <CheckCircle className="w-5 h-5" />
                  Last Broadcast Sent
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <p className="text-sm text-green-800">
                  {lastBroadcast.message.length > 100
                    ? `${lastBroadcast.message.substring(0, 100)}...`
                    : lastBroadcast.message}
                </p>
                <div className="text-xs text-green-600 space-y-1">
                  <p>Recipients: {lastBroadcast.recipients} users</p>
                    <p>Sent: {formatDateTime(lastBroadcast.timestamp, { dateStyle: 'medium', timeStyle: 'short' })}</p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Tips */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Tips</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-muted-foreground space-y-2 list-disc list-inside">
                <li>Keep messages concise and actionable</li>
                <li>Use clear language without jargon</li>
                <li>Include relevant links or CTAs</li>
                <li>Test with a small group first if needed</li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

const API_URL = typeof window !== 'undefined'
  ? (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://api.nabavkidata.com')
  : 'https://api.nabavkidata.com';

interface Payout {
  payout_id: string;
  user_email: string;
  amount_cents: number;
  currency: string;
  status: string;
  bank_name: string | null;
  account_holder: string | null;
  iban: string | null;
  requested_at: string | null;
  paid_at: string | null;
  admin_notes: string | null;
}

export default function AdminReferralsPage() {
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('pending');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const getToken = () => localStorage.getItem('auth_token');

  const fetchPayouts = async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/referrals/payouts?payout_status=${filter}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (res.ok) {
        const data = await res.json();
        setPayouts(data.payouts || []);
      }
    } catch (err) {
      console.error('Failed to fetch payouts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchPayouts();
  }, [filter]);

  const handleComplete = async (payoutId: string) => {
    setActionLoading(payoutId);
    try {
      const res = await fetch(`${API_URL}/api/admin/referrals/payouts/${payoutId}/complete`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ admin_notes: 'Paid via bank transfer' }),
      });
      if (res.ok) {
        fetchPayouts();
      }
    } catch (err) {
      console.error('Failed to complete payout:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (payoutId: string) => {
    const reason = prompt('Reason for rejection:');
    if (!reason) return;

    setActionLoading(payoutId);
    try {
      const res = await fetch(`${API_URL}/api/admin/referrals/payouts/${payoutId}/reject`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${getToken()}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ admin_notes: reason }),
      });
      if (res.ok) {
        fetchPayouts();
      }
    } catch (err) {
      console.error('Failed to reject payout:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const formatEur = (cents: number) => `€${(cents / 100).toFixed(2)}`;

  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    approved: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    rejected: 'bg-red-100 text-red-800',
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Referral Payouts</h1>
        <p className="text-muted-foreground">Manage referral program payout requests</p>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {['pending', 'completed', 'rejected', 'all'].map((f) => (
          <Button
            key={f}
            variant={filter === f ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </Button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Payout Requests</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground text-sm">Loading...</p>
          ) : payouts.length === 0 ? (
            <p className="text-muted-foreground text-sm">No payout requests found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 px-2">User</th>
                    <th className="text-right py-2 px-2">Amount</th>
                    <th className="text-left py-2 px-2">Bank</th>
                    <th className="text-left py-2 px-2">IBAN</th>
                    <th className="text-left py-2 px-2">Status</th>
                    <th className="text-left py-2 px-2">Requested</th>
                    <th className="text-right py-2 px-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {payouts.map((p) => (
                    <tr key={p.payout_id} className="border-b last:border-0">
                      <td className="py-2 px-2">{p.user_email}</td>
                      <td className="py-2 px-2 text-right font-medium">{formatEur(p.amount_cents)}</td>
                      <td className="py-2 px-2 text-xs">{p.account_holder}<br/><span className="text-muted-foreground">{p.bank_name}</span></td>
                      <td className="py-2 px-2 font-mono text-xs">{p.iban}</td>
                      <td className="py-2 px-2">
                        <Badge className={statusColors[p.status] || ''} variant="secondary">
                          {p.status}
                        </Badge>
                      </td>
                      <td className="py-2 px-2 text-xs">
                        {p.requested_at ? new Date(p.requested_at).toLocaleDateString('mk-MK') : '-'}
                      </td>
                      <td className="py-2 px-2 text-right">
                        {p.status === 'pending' && (
                          <div className="flex gap-1 justify-end">
                            <Button
                              size="sm"
                              variant="default"
                              onClick={() => handleComplete(p.payout_id)}
                              disabled={actionLoading === p.payout_id}
                            >
                              {actionLoading === p.payout_id ? '...' : 'Paid'}
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleReject(p.payout_id)}
                              disabled={actionLoading === p.payout_id}
                            >
                              Reject
                            </Button>
                          </div>
                        )}
                        {p.admin_notes && (
                          <p className="text-xs text-muted-foreground mt-1">{p.admin_notes}</p>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

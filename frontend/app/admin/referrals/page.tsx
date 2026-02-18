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

interface Referrer {
  email: string;
  stripe_connect_status: string | null;
  total_earned_cents: number;
  total_paid_out_cents: number;
  pending_balance_cents: number;
  active_referrals: number;
  total_referrals: number;
}

export default function AdminReferralsPage() {
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [referrers, setReferrers] = useState<Referrer[]>([]);
  const [loading, setLoading] = useState(true);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [filter, setFilter] = useState('pending');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'payouts'>('dashboard');

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

  const fetchDashboard = async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/referrals/dashboard`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (res.ok) {
        const data = await res.json();
        setReferrers(data.referrers || []);
      }
    } catch (err) {
      console.error('Failed to fetch dashboard:', err);
    } finally {
      setDashboardLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

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

  const connectStatusColors: Record<string, string> = {
    active: 'bg-green-100 text-green-800',
    pending: 'bg-yellow-100 text-yellow-800',
    restricted: 'bg-orange-100 text-orange-800',
  };

  const totalOwed = referrers.reduce((sum, r) => sum + r.pending_balance_cents, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Referral Program</h1>
        <p className="text-muted-foreground">Manage referrals, balances, and payout requests</p>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-2">
        <Button
          variant={activeTab === 'dashboard' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setActiveTab('dashboard')}
        >
          Balances Dashboard
        </Button>
        <Button
          variant={activeTab === 'payouts' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setActiveTab('payouts')}
        >
          Payout Requests
        </Button>
      </div>

      {/* Dashboard Tab */}
      {activeTab === 'dashboard' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Referrer Balances</span>
              {totalOwed > 0 && (
                <Badge className="bg-blue-100 text-blue-800 text-sm">
                  Total owed: {formatEur(totalOwed)}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboardLoading ? (
              <p className="text-muted-foreground text-sm">Loading...</p>
            ) : referrers.length === 0 ? (
              <p className="text-muted-foreground text-sm">No referrers with earnings yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 px-2">Email</th>
                      <th className="text-right py-2 px-2">Earned</th>
                      <th className="text-right py-2 px-2">Paid Out</th>
                      <th className="text-right py-2 px-2">Balance</th>
                      <th className="text-center py-2 px-2">Referrals</th>
                      <th className="text-left py-2 px-2">Stripe</th>
                    </tr>
                  </thead>
                  <tbody>
                    {referrers.map((r) => (
                      <tr key={r.email} className="border-b last:border-0">
                        <td className="py-2 px-2">{r.email}</td>
                        <td className="py-2 px-2 text-right">{formatEur(r.total_earned_cents)}</td>
                        <td className="py-2 px-2 text-right">{formatEur(r.total_paid_out_cents)}</td>
                        <td className="py-2 px-2 text-right font-medium">
                          {r.pending_balance_cents > 0 ? (
                            <span className="text-green-700">{formatEur(r.pending_balance_cents)}</span>
                          ) : (
                            formatEur(0)
                          )}
                        </td>
                        <td className="py-2 px-2 text-center">
                          {r.active_referrals}/{r.total_referrals}
                        </td>
                        <td className="py-2 px-2">
                          {r.stripe_connect_status ? (
                            <Badge className={connectStatusColors[r.stripe_connect_status] || ''} variant="secondary">
                              {r.stripe_connect_status}
                            </Badge>
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
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
      )}

      {/* Payouts Tab */}
      {activeTab === 'payouts' && (
        <>
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
        </>
      )}
    </div>
  );
}

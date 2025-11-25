'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Search, CheckCircle, XCircle, Edit, Trash2 } from 'lucide-react';
import { toast } from "sonner";

interface Tender {
  id: string;
  tender_id?: string;
  title: string;
  category: string;
  status: string;
  budget: number;
  organization: string;
  deadline: string;
  created_at: string;
}

// Backend response format
interface BackendTender {
  tender_id: string;
  title: string;
  category: string | null;
  procuring_entity: string | null;
  status: string | null;
  publication_date: string | null;
  closing_date: string | null;
  estimated_value_mkd: string | null;
}

export default function AdminTendersPage() {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [filteredTenders, setFilteredTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTender, setSelectedTender] = useState<Tender | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  const [filters, setFilters] = useState({
    status: 'all',
    category: 'all',
    search: '',
  });

  const [pagination, setPagination] = useState({
    page: 1,
    limit: 20,
    total: 0,
  });

  useEffect(() => {
    fetchTenders();
  }, [pagination.page]);

  useEffect(() => {
    applyFilters();
  }, [tenders, filters]);

  const encodeTenderId = (id: string) => encodeURIComponent(id);

  const fetchTenders = async () => {
    try {
      setLoading(true);

      const params = new URLSearchParams({
        page: pagination.page.toString(),
        limit: pagination.limit.toString(),
      });

      const response = await fetch(`/api/admin/tenders?${params}`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        // Map backend response to frontend format
        const mappedTenders = (data.tenders || []).map((t: BackendTender) => ({
          id: t.tender_id,
          tender_id: t.tender_id,
          title: t.title || '',
          category: t.category || 'Other',
          status: t.status || 'open',
          budget: parseFloat(t.estimated_value_mkd || '0') || 0,
          organization: t.procuring_entity || '',
          deadline: t.closing_date || '',
          created_at: t.publication_date || '',
        }));
        setTenders(mappedTenders);
        setPagination((prev) => ({ ...prev, total: data.total }));
      }
    } catch (error) {
      console.error('Error fetching tenders:', error);
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    const filtered = tenders.filter((tender) => {
      if (filters.status !== 'all' && tender.status !== filters.status) return false;
      if (filters.category !== 'all' && tender.category !== filters.category) return false;
      if (filters.search) {
        const search = filters.search.toLowerCase();
        if (!tender.title.toLowerCase().includes(search) && !tender.organization.toLowerCase().includes(search)) return false;
      }
      return true;
    });
    setFilteredTenders(filtered);
  };

  const handleTenderAction = async (tenderId: string, action: 'approve' | 'reject', needsConfirm = false) => {
    if (needsConfirm && !confirm(`Are you sure you want to ${action} this tender?`)) return;
    try {
      const response = await fetch(`/api/admin/tenders/${encodeTenderId(tenderId)}/${action}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      });
      if (response.ok) {
        fetchTenders();
        toast.success(`Tender ${action === 'approve' ? 'approved' : 'rejected'} successfully`);
      } else {
        toast.error(`Error ${action === 'approve' ? 'approving' : 'rejecting'} tender`);
      }
    } catch (error) {
      console.error(`Error ${action} tender:`, error);
      toast.error(`Error ${action === 'approve' ? 'approving' : 'rejecting'} tender`);
    }
  };

  const handleApprove = (tenderId: string) => handleTenderAction(tenderId, 'approve');
  const handleReject = (tenderId: string) => handleTenderAction(tenderId, 'reject', true);

  const handleEdit = (tender: Tender) => {
    setSelectedTender(tender);
    setIsEditModalOpen(true);
  };

  const handleSaveTender = async () => {
    if (!selectedTender) return;

    try {
      const response = await fetch(`/api/admin/tenders/${encodeTenderId(selectedTender.id)}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
        body: JSON.stringify(selectedTender),
      });

      if (response.ok) {
        toast.success('Tender saved successfully');
        fetchTenders();
        setIsEditModalOpen(false);
        setSelectedTender(null);
      } else {
        toast.error('Error saving tender');
      }
    } catch (error) {
      console.error('Error saving tender:', error);
      toast.error('Error saving tender');
    }
  };

  const handleDelete = async (tenderId: string) => {
    if (!confirm('Are you sure you want to delete this tender?'))
      return;

    try {
      const response = await fetch(`/api/admin/tenders/${encodeTenderId(tenderId)}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });

      if (response.ok) {
        fetchTenders();
        toast.success('Tender deleted successfully');
      } else {
        toast.error('Error deleting tender');
      }
    } catch (error) {
      console.error('Error deleting tender:', error);
      toast.error('Error deleting tender');
    }
  };

  const statusConfig: Record<string, { color: string; label: string }> = {
    pending: { color: 'bg-yellow-100 text-yellow-800', label: 'Pending' },
    approved: { color: 'bg-green-100 text-green-800', label: 'Approved' },
    rejected: { color: 'bg-red-100 text-red-800', label: 'Rejected' },
    active: { color: 'bg-blue-100 text-blue-800', label: 'Active' },
    open: { color: 'bg-blue-100 text-blue-800', label: 'Open' },
    closed: { color: 'bg-gray-100 text-gray-800', label: 'Closed' },
    awarded: { color: 'bg-green-100 text-green-800', label: 'Awarded' },
  };

  const getStatusBadge = (status: string) => {
    const { color, label } = statusConfig[status] || { color: 'bg-gray-100 text-gray-800', label: status };
    return <Badge className={color}>{label}</Badge>;
  };

  const totalPages = Math.ceil(pagination.total / pagination.limit);

  if (loading && tenders.length === 0) return <div className="flex items-center justify-center min-h-screen"><div className="text-center"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div><p className="mt-4 text-muted-foreground">Loading...</p></div></div>;

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Tender Management</h1>
        <p className="text-muted-foreground mt-1">Total {pagination.total} tenders</p>
      </div>

      <Card>
        <CardHeader><CardTitle>Filters</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" /><Input placeholder="Search by title or organization..." className="pl-10" value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} /></div>
            <Select value={filters.status} onValueChange={(value) => setFilters({ ...filters, status: value })}><SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger><SelectContent><SelectItem value="all">All Statuses</SelectItem><SelectItem value="pending">Pending</SelectItem><SelectItem value="open">Open</SelectItem><SelectItem value="closed">Closed</SelectItem><SelectItem value="awarded">Awarded</SelectItem></SelectContent></Select>
            <Select value={filters.category} onValueChange={(value) => setFilters({ ...filters, category: value })}><SelectTrigger><SelectValue placeholder="Category" /></SelectTrigger><SelectContent><SelectItem value="all">All Categories</SelectItem><SelectItem value="Работи">Works</SelectItem><SelectItem value="Стоки">Goods</SelectItem><SelectItem value="Услуги">Services</SelectItem></SelectContent></Select>
          </div>
        </CardContent>
      </Card>

      {/* Tenders Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead>Organization</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Budget (MKD)</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Deadline</TableHead>
              <TableHead className="w-[150px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredTenders.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  No tenders
                </TableCell>
              </TableRow>
            ) : (
              filteredTenders.map((tender) => (
                <TableRow key={tender.id}>
                  <TableCell className="font-medium max-w-[300px] truncate">
                    {tender.title}
                  </TableCell>
                  <TableCell>{tender.organization}</TableCell>
                  <TableCell>{tender.category}</TableCell>
                  <TableCell>€{tender.budget.toLocaleString()}</TableCell>
                  <TableCell>{getStatusBadge(tender.status)}</TableCell>
                  <TableCell>
                    {new Date(tender.deadline).toLocaleDateString('mk-MK')}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {tender.status === 'pending' && (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleApprove(tender.id)}
                            title="Одобри"
                          >
                            <CheckCircle className="w-4 h-4 text-green-600" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleReject(tender.id)}
                            title="Одбиј"
                          >
                            <XCircle className="w-4 h-4 text-red-600" />
                          </Button>
                        </>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleEdit(tender)}
                        title="Измени"
                      >
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDelete(tender.id)}
                        title="Избриши"
                      >
                        <Trash2 className="w-4 h-4 text-red-600" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Page {pagination.page} of {totalPages}</p>
        <div className="flex gap-2">
          <Button variant="outline" disabled={pagination.page === 1} onClick={() => setPagination({ ...pagination, page: pagination.page - 1 })}>Previous</Button>
          <Button variant="outline" disabled={pagination.page >= totalPages} onClick={() => setPagination({ ...pagination, page: pagination.page + 1 })}>Next</Button>
        </div>
      </div>

      <Dialog open={isEditModalOpen} onOpenChange={setIsEditModalOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Edit Tender</DialogTitle></DialogHeader>
          {selectedTender && (
            <div className="space-y-4 max-h-[60vh] overflow-y-auto">
              <div><Label>Title</Label><Input value={selectedTender.title} onChange={(e) => setSelectedTender({ ...selectedTender, title: e.target.value })} /></div>
              <div><Label>Organization</Label><Input value={selectedTender.organization} onChange={(e) => setSelectedTender({ ...selectedTender, organization: e.target.value })} /></div>
              <div>
                <Label>Category</Label>
                <Select value={selectedTender.category} onValueChange={(value) => setSelectedTender({ ...selectedTender, category: value })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Работи">Works</SelectItem>
                    <SelectItem value="Стоки">Goods</SelectItem>
                    <SelectItem value="Услуги">Services</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Budget (MKD)</Label><Input type="number" value={selectedTender.budget} onChange={(e) => setSelectedTender({ ...selectedTender, budget: parseFloat(e.target.value) })} /></div>
              <div>
                <Label>Status</Label>
                <Select value={selectedTender.status} onValueChange={(value) => setSelectedTender({ ...selectedTender, status: value })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="open">Open</SelectItem>
                    <SelectItem value="closed">Closed</SelectItem>
                    <SelectItem value="awarded">Awarded</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Deadline</Label><Input type="date" value={selectedTender.deadline ? new Date(selectedTender.deadline).toISOString().split('T')[0] : ''} onChange={(e) => setSelectedTender({ ...selectedTender, deadline: e.target.value })} /></div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditModalOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveTender}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

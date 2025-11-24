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
  title: string;
  category: string;
  status: string;
  budget: number;
  organization: string;
  deadline: string;
  created_at: string;
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
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setTenders(data.tenders);
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
    if (needsConfirm && !confirm(`Дали сте сигурни дека сакате да го ${action === 'approve' ? 'одобрите' : 'одбиете'} тендерот?`)) return;
    try {
      const response = await fetch(`/api/admin/tenders/${encodeTenderId(tenderId)}/${action}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (response.ok) {
        fetchTenders();
        toast.success(`Тендерот е успешно ${action === 'approve' ? 'одобрен' : 'одбиен'}`);
      } else {
        toast.error(`Грешка при ${action === 'approve' ? 'одобрување' : 'одбивање'} на тендерот`);
      }
    } catch (error) {
      console.error(`Error ${action} tender:`, error);
      toast.error(`Грешка при ${action === 'approve' ? 'одобрување' : 'одбивање'} на тендерот`);
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
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify(selectedTender),
      });

      if (response.ok) {
        toast.success('Тендерот е успешно зачуван');
        fetchTenders();
        setIsEditModalOpen(false);
        setSelectedTender(null);
      } else {
        toast.error('Грешка при зачувување на тендерот');
      }
    } catch (error) {
      console.error('Error saving tender:', error);
      toast.error('Грешка при зачувување на тендерот');
    }
  };

  const handleDelete = async (tenderId: string) => {
    if (!confirm('Дали сте сигурни дека сакате да го избришете тендерот?'))
      return;

    try {
      const response = await fetch(`/api/admin/tenders/${encodeTenderId(tenderId)}`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (response.ok) {
        fetchTenders();
        toast.success('Тендерот е успешно избришан');
      } else {
        toast.error('Грешка при бришење на тендерот');
      }
    } catch (error) {
      console.error('Error deleting tender:', error);
      toast.error('Грешка при бришење на тендерот');
    }
  };

  const statusConfig: Record<string, { color: string; label: string }> = {
    pending: { color: 'bg-yellow-100 text-yellow-800', label: 'Во очекување' },
    approved: { color: 'bg-green-100 text-green-800', label: 'Одобрен' },
    rejected: { color: 'bg-red-100 text-red-800', label: 'Одбиен' },
    active: { color: 'bg-blue-100 text-blue-800', label: 'Активен' },
    closed: { color: 'bg-gray-100 text-gray-800', label: 'Затворен' },
  };

  const getStatusBadge = (status: string) => {
    const { color, label } = statusConfig[status] || { color: 'bg-gray-100 text-gray-800', label: status };
    return <Badge className={color}>{label}</Badge>;
  };

  const totalPages = Math.ceil(pagination.total / pagination.limit);

  if (loading && tenders.length === 0) return <div className="flex items-center justify-center min-h-screen"><div className="text-center"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div><p className="mt-4 text-muted-foreground">Се вчитува...</p></div></div>;

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Управување со тендери</h1>
        <p className="text-muted-foreground mt-1">Вкупно {pagination.total} тендери</p>
      </div>

      <Card>
        <CardHeader><CardTitle>Филтри</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" /><Input placeholder="Пребарај по наслов или организација..." className="pl-10" value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} /></div>
            <Select value={filters.status} onValueChange={(value) => setFilters({ ...filters, status: value })}><SelectTrigger><SelectValue placeholder="Статус" /></SelectTrigger><SelectContent><SelectItem value="all">Сите статуси</SelectItem><SelectItem value="pending">Во очекување</SelectItem><SelectItem value="approved">Одобрен</SelectItem><SelectItem value="rejected">Одбиен</SelectItem><SelectItem value="active">Активен</SelectItem><SelectItem value="closed">Затворен</SelectItem></SelectContent></Select>
            <Select value={filters.category} onValueChange={(value) => setFilters({ ...filters, category: value })}><SelectTrigger><SelectValue placeholder="Категорија" /></SelectTrigger><SelectContent><SelectItem value="all">Сите категории</SelectItem><SelectItem value="construction">Градежништво</SelectItem><SelectItem value="it">ИТ и телекомуникации</SelectItem><SelectItem value="services">Услуги</SelectItem><SelectItem value="supplies">Снабдување</SelectItem></SelectContent></Select>
          </div>
        </CardContent>
      </Card>

      {/* Tenders Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Наслов</TableHead>
              <TableHead>Организација</TableHead>
              <TableHead>Категорија</TableHead>
              <TableHead>Буџет</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead>Краен рок</TableHead>
              <TableHead className="w-[150px]">Акции</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredTenders.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  Нема тендери
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
        <p className="text-sm text-muted-foreground">Страна {pagination.page} од {totalPages}</p>
        <div className="flex gap-2">
          <Button variant="outline" disabled={pagination.page === 1} onClick={() => setPagination({ ...pagination, page: pagination.page - 1 })}>Претходна</Button>
          <Button variant="outline" disabled={pagination.page >= totalPages} onClick={() => setPagination({ ...pagination, page: pagination.page + 1 })}>Следна</Button>
        </div>
      </div>

      <Dialog open={isEditModalOpen} onOpenChange={setIsEditModalOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Измени тендер</DialogTitle></DialogHeader>
          {selectedTender && (
            <div className="space-y-4 max-h-[60vh] overflow-y-auto">
              <div><Label>Наслов</Label><Input value={selectedTender.title} onChange={(e) => setSelectedTender({ ...selectedTender, title: e.target.value })} /></div>
              <div><Label>Организација</Label><Input value={selectedTender.organization} onChange={(e) => setSelectedTender({ ...selectedTender, organization: e.target.value })} /></div>
              <div>
                <Label>Категорија</Label>
                <Select value={selectedTender.category} onValueChange={(value) => setSelectedTender({ ...selectedTender, category: value })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="construction">Градежништво</SelectItem>
                    <SelectItem value="it">ИТ и телекомуникации</SelectItem>
                    <SelectItem value="services">Услуги</SelectItem>
                    <SelectItem value="supplies">Снабдување</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Буџет (€)</Label><Input type="number" value={selectedTender.budget} onChange={(e) => setSelectedTender({ ...selectedTender, budget: parseFloat(e.target.value) })} /></div>
              <div>
                <Label>Статус</Label>
                <Select value={selectedTender.status} onValueChange={(value) => setSelectedTender({ ...selectedTender, status: value })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="pending">Во очекување</SelectItem>
                    <SelectItem value="approved">Одобрен</SelectItem>
                    <SelectItem value="rejected">Одбиен</SelectItem>
                    <SelectItem value="active">Активен</SelectItem>
                    <SelectItem value="closed">Затворен</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Краен рок</Label><Input type="date" value={selectedTender.deadline ? new Date(selectedTender.deadline).toISOString().split('T')[0] : ''} onChange={(e) => setSelectedTender({ ...selectedTender, deadline: e.target.value })} /></div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditModalOpen(false)}>Откажи</Button>
            <Button onClick={handleSaveTender}>Зачувај</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

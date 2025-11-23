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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import UserTable from '@/components/admin/UserTable';
import { Search, Filter, Download, UserPlus } from 'lucide-react';
import { toast } from "sonner";

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  status: string;
  subscription: string;
  verified: boolean;
  created_at: string;
}

interface Filters {
  role: string;
  status: string;
  subscription: string;
  verified: string;
  search: string;
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [filteredUsers, setFilteredUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [selectedUsers, setSelectedUsers] = useState<string[]>([]);

  const [filters, setFilters] = useState<Filters>({
    role: 'all',
    status: 'all',
    subscription: 'all',
    verified: 'all',
    search: '',
  });

  const [pagination, setPagination] = useState({
    page: 1,
    limit: 20,
    total: 0,
  });

  useEffect(() => {
    fetchUsers();
  }, [pagination.page]);

  useEffect(() => {
    applyFilters();
  }, [users, filters]);

  const fetchUsers = async () => {
    try {
      setLoading(true);

      const params = new URLSearchParams({
        page: pagination.page.toString(),
        limit: pagination.limit.toString(),
      });

      const response = await fetch(`/api/admin/users?${params}`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setUsers(data.users);
        setPagination((prev) => ({ ...prev, total: data.total }));
      } else {
        console.error('Failed to fetch users');
      }
    } catch (error) {
      console.error('Error fetching users:', error);
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    let filtered = users.filter((user) => {
      if (filters.role !== 'all' && user.role !== filters.role) return false;
      if (filters.status !== 'all' && user.status !== filters.status) return false;
      if (filters.subscription !== 'all' && user.subscription !== filters.subscription) return false;
      if (filters.verified !== 'all' && user.verified !== (filters.verified === 'true')) return false;
      if (filters.search) {
        const search = filters.search.toLowerCase();
        if (!user.email.toLowerCase().includes(search) && !user.name.toLowerCase().includes(search)) return false;
      }
      return true;
    });
    setFilteredUsers(filtered);
  };

  const handleEdit = (user: User) => {
    setSelectedUser(user);
    setIsEditModalOpen(true);
  };

  const handleSaveUser = async () => {
    if (!selectedUser) return;

    try {
      const response = await fetch(`/api/admin/users/${selectedUser.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify(selectedUser),
      });

      if (response.ok) {
        fetchUsers();
        setIsEditModalOpen(false);
        setSelectedUser(null);
        toast.success('Корисникот е успешно зачуван');
      } else {
        toast.error('Грешка при зачувување на корисникот');
      }
    } catch (error) {
      console.error('Error saving user:', error);
      toast.error('Грешка при зачувување на корисникот');
    }
  };

  const handleAction = async (userId: string, action: string, method = 'POST') => {
    const confirmMsg = action === 'delete' ? 'избришете' : action === 'ban' ? 'банирате' : '';
    if (confirmMsg && !confirm(`Дали сте сигурни дека сакате да го ${confirmMsg} корисникот?`)) return;

    try {
      const endpoint = action === 'delete' ? `/api/admin/users/${userId}` : `/api/admin/users/${userId}/${action}`;
      const response = await fetch(endpoint, {
        method: action === 'delete' ? 'DELETE' : method,
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (response.ok) {
        fetchUsers();
        toast.success('Акцијата е успешно извршена');
      } else {
        toast.error(`Грешка при ${action === 'verify' ? 'верификација' : action === 'ban' ? 'банирање' : 'бришење'} на корисникот`);
      }
    } catch (error) {
      console.error(`Error ${action} user:`, error);
      toast.error(`Грешка при ${action === 'verify' ? 'верификација' : action === 'ban' ? 'банирање' : 'бришење'} на корисникот`);
    }
  };

  const handleBan = (userId: string) => handleAction(userId, 'ban');
  const handleDelete = (userId: string) => handleAction(userId, 'delete');
  const handleVerify = (userId: string) => handleAction(userId, 'verify');

  const handleBulkAction = async (action: string) => {
    if (selectedUsers.length === 0) {
      toast.error('Изберете барем еден корисник');
      return;
    }

    if (!confirm(`Дали сте сигурни дека сакате да ${action} ${selectedUsers.length} корисници?`))
      return;

    try {
      const response = await fetch('/api/admin/users/bulk', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          action,
          userIds: selectedUsers,
        }),
      });

      if (response.ok) {
        fetchUsers();
        setSelectedUsers([]);
        toast.success('Акцијата е успешно извршена');
      } else {
        toast.error('Грешка при извршување на акцијата');
      }
    } catch (error) {
      console.error('Error performing bulk action:', error);
      toast.error('Грешка при извршување на акцијата');
    }
  };

  const handleExport = async () => {
    try {
      const response = await fetch('/api/admin/users/export', {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `users-${new Date().toISOString()}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Error exporting users:', error);
      toast.error('Грешка при експорт на корисниците');
    }
  };

  const totalPages = Math.ceil(pagination.total / pagination.limit);

  if (loading && users.length === 0) return <div className="flex items-center justify-center min-h-screen"><div className="text-center"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div><p className="mt-4 text-muted-foreground">Се вчитува...</p></div></div>;

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Управување со корисници</h1>
          <p className="text-muted-foreground mt-1">Вкупно {pagination.total} корисници</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExport}><Download className="w-4 h-4 mr-2" />Експортирај</Button>
          <Button><UserPlus className="w-4 h-4 mr-2" />Додади корисник</Button>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle>Филтри</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" /><Input placeholder="Пребарај по email или име..." className="pl-10" value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} /></div>
            <Select value={filters.role} onValueChange={(value) => setFilters({ ...filters, role: value })}><SelectTrigger><SelectValue placeholder="Улога" /></SelectTrigger><SelectContent><SelectItem value="all">Сите улоги</SelectItem><SelectItem value="admin">Админ</SelectItem><SelectItem value="moderator">Модератор</SelectItem><SelectItem value="user">Корисник</SelectItem></SelectContent></Select>
            <Select value={filters.status} onValueChange={(value) => setFilters({ ...filters, status: value })}><SelectTrigger><SelectValue placeholder="Статус" /></SelectTrigger><SelectContent><SelectItem value="all">Сите статуси</SelectItem><SelectItem value="active">Активен</SelectItem><SelectItem value="inactive">Неактивен</SelectItem><SelectItem value="banned">Банан</SelectItem></SelectContent></Select>
            <Select value={filters.subscription} onValueChange={(value) => setFilters({ ...filters, subscription: value })}><SelectTrigger><SelectValue placeholder="Претплата" /></SelectTrigger><SelectContent><SelectItem value="all">Сите претплати</SelectItem><SelectItem value="free">Бесплатен</SelectItem><SelectItem value="basic">Основен</SelectItem><SelectItem value="premium">Премиум</SelectItem><SelectItem value="enterprise">Корпоративен</SelectItem></SelectContent></Select>
            <Select value={filters.verified} onValueChange={(value) => setFilters({ ...filters, verified: value })}><SelectTrigger><SelectValue placeholder="Верификација" /></SelectTrigger><SelectContent><SelectItem value="all">Сите</SelectItem><SelectItem value="true">Верифицирани</SelectItem><SelectItem value="false">Неверифицирани</SelectItem></SelectContent></Select>
          </div>
        </CardContent>
      </Card>

      {selectedUsers.length > 0 && <Card><CardContent className="py-4 flex items-center justify-between"><p className="text-sm font-medium">{selectedUsers.length} корисници избрани</p><div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => handleBulkAction('verify')}>Верифицирај</Button><Button variant="outline" size="sm" onClick={() => handleBulkAction('ban')}>Банирај</Button><Button variant="destructive" size="sm" onClick={() => handleBulkAction('delete')}>Избриши</Button></div></CardContent></Card>}

      <UserTable users={filteredUsers} onEdit={handleEdit} onBan={handleBan} onDelete={handleDelete} onVerify={handleVerify} />

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Страна {pagination.page} од {totalPages}</p>
        <div className="flex gap-2">
          <Button variant="outline" disabled={pagination.page === 1} onClick={() => setPagination({ ...pagination, page: pagination.page - 1 })}>Претходна</Button>
          <Button variant="outline" disabled={pagination.page >= totalPages} onClick={() => setPagination({ ...pagination, page: pagination.page + 1 })}>Следна</Button>
        </div>
      </div>

      <Dialog open={isEditModalOpen} onOpenChange={setIsEditModalOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Измени корисник</DialogTitle></DialogHeader>
          {selectedUser && (
            <div className="space-y-4">
              <div><Label>Email</Label><Input value={selectedUser.email} onChange={(e) => setSelectedUser({ ...selectedUser, email: e.target.value })} /></div>
              <div><Label>Име</Label><Input value={selectedUser.name} onChange={(e) => setSelectedUser({ ...selectedUser, name: e.target.value })} /></div>
              <div>
                <Label>Улога</Label>
                <Select value={selectedUser.role} onValueChange={(value) => setSelectedUser({ ...selectedUser, role: value })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">Админ</SelectItem>
                    <SelectItem value="moderator">Модератор</SelectItem>
                    <SelectItem value="user">Корисник</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Статус</Label>
                <Select value={selectedUser.status} onValueChange={(value) => setSelectedUser({ ...selectedUser, status: value })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Активен</SelectItem>
                    <SelectItem value="inactive">Неактивен</SelectItem>
                    <SelectItem value="banned">Банан</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditModalOpen(false)}>Откажи</Button>
            <Button onClick={handleSaveUser}>Зачувај</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

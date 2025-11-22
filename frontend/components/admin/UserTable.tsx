'use client';

import { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { MoreVertical, Edit, Ban, Trash2, CheckCircle } from 'lucide-react';

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

interface UserTableProps {
  users: User[];
  onEdit: (user: User) => void;
  onBan: (userId: string) => void;
  onDelete: (userId: string) => void;
  onVerify: (userId: string) => void;
}

export default function UserTable({
  users,
  onEdit,
  onBan,
  onDelete,
  onVerify,
}: UserTableProps) {
  const [sortField, setSortField] = useState<keyof User>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const handleSort = (field: keyof User) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const sortedUsers = [...users].sort((a, b) => {
    const aVal = a[sortField];
    const bVal = b[sortField];

    if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
    if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  const getRoleBadge = (role: string) => {
    const colors: Record<string, string> = {
      admin: 'bg-red-100 text-red-800',
      user: 'bg-blue-100 text-blue-800',
      moderator: 'bg-purple-100 text-purple-800',
    };

    return (
      <Badge className={colors[role] || 'bg-gray-100 text-gray-800'}>
        {role === 'admin' ? 'Админ' : role === 'moderator' ? 'Модератор' : 'Корисник'}
      </Badge>
    );
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      active: 'bg-green-100 text-green-800',
      inactive: 'bg-gray-100 text-gray-800',
      banned: 'bg-red-100 text-red-800',
    };

    return (
      <Badge className={colors[status] || 'bg-gray-100 text-gray-800'}>
        {status === 'active' ? 'Активен' : status === 'banned' ? 'Банан' : 'Неактивен'}
      </Badge>
    );
  };

  const getSubscriptionBadge = (subscription: string) => {
    const colors: Record<string, string> = {
      free: 'bg-gray-100 text-gray-800',
      basic: 'bg-blue-100 text-blue-800',
      premium: 'bg-purple-100 text-purple-800',
      enterprise: 'bg-yellow-100 text-yellow-800',
    };

    return (
      <Badge className={colors[subscription] || 'bg-gray-100 text-gray-800'}>
        {subscription === 'free'
          ? 'Бесплатен'
          : subscription === 'basic'
          ? 'Основен'
          : subscription === 'premium'
          ? 'Премиум'
          : 'Корпоративен'}
      </Badge>
    );
  };

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead
              className="cursor-pointer"
              onClick={() => handleSort('email')}
            >
              Email
            </TableHead>
            <TableHead
              className="cursor-pointer"
              onClick={() => handleSort('name')}
            >
              Име
            </TableHead>
            <TableHead
              className="cursor-pointer"
              onClick={() => handleSort('role')}
            >
              Улога
            </TableHead>
            <TableHead
              className="cursor-pointer"
              onClick={() => handleSort('status')}
            >
              Статус
            </TableHead>
            <TableHead
              className="cursor-pointer"
              onClick={() => handleSort('subscription')}
            >
              Претплата
            </TableHead>
            <TableHead>Верифициран</TableHead>
            <TableHead
              className="cursor-pointer"
              onClick={() => handleSort('created_at')}
            >
              Креиран
            </TableHead>
            <TableHead className="w-[70px]">Акции</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedUsers.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} className="text-center py-8">
                Нема корисници
              </TableCell>
            </TableRow>
          ) : (
            sortedUsers.map((user) => (
              <TableRow key={user.id}>
                <TableCell className="font-medium">{user.email}</TableCell>
                <TableCell>{user.name}</TableCell>
                <TableCell>{getRoleBadge(user.role)}</TableCell>
                <TableCell>{getStatusBadge(user.status)}</TableCell>
                <TableCell>{getSubscriptionBadge(user.subscription)}</TableCell>
                <TableCell>
                  {user.verified ? (
                    <CheckCircle className="w-4 h-4 text-green-600" />
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </TableCell>
                <TableCell>
                  {new Date(user.created_at).toLocaleDateString('mk-MK')}
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm">
                        <MoreVertical className="w-4 h-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => onEdit(user)}>
                        <Edit className="w-4 h-4 mr-2" />
                        Измени
                      </DropdownMenuItem>
                      {!user.verified && (
                        <DropdownMenuItem onClick={() => onVerify(user.id)}>
                          <CheckCircle className="w-4 h-4 mr-2" />
                          Верифицирај
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem onClick={() => onBan(user.id)}>
                        <Ban className="w-4 h-4 mr-2" />
                        {user.status === 'banned' ? 'Одбанај' : 'Банирај'}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => onDelete(user.id)}
                        className="text-red-600"
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Избриши
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}

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
import { formatDate } from '@/lib/utils';

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
      admin: 'bg-red-600 text-white',
      user: 'bg-blue-600 text-white',
      moderator: 'bg-purple-600 text-white',
    };

    return (
      <Badge className={colors[role] || 'bg-gray-600 text-white'}>
        {role === 'admin' ? 'Админ' : role === 'moderator' ? 'Модератор' : 'Корисник'}
      </Badge>
    );
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      active: 'bg-green-600 text-white',
      inactive: 'bg-gray-500 text-white',
      banned: 'bg-red-600 text-white',
    };

    return (
      <Badge className={colors[status] || 'bg-gray-500 text-white'}>
        {status === 'active' ? 'Активен' : status === 'banned' ? 'Баниран' : 'Неактивен'}
      </Badge>
    );
  };

  const getSubscriptionBadge = (subscription: string) => {
    const colors: Record<string, string> = {
      free: 'bg-gray-500 text-white',
      starter: 'bg-blue-600 text-white',
      professional: 'bg-purple-600 text-white',
      enterprise: 'bg-amber-600 text-white',
    };

    const labels: Record<string, string> = {
      free: 'Free',
      starter: 'Starter',
      professional: 'Pro',
      enterprise: 'Enterprise',
    };

    return (
      <Badge className={colors[subscription] || 'bg-gray-500 text-white'}>
        {labels[subscription] || subscription}
      </Badge>
    );
  };

  return (
    <div className="rounded-md border bg-white">
      <Table>
        <TableHeader>
          <TableRow className="bg-gray-50">
            <TableHead
              className="cursor-pointer text-gray-900 font-semibold"
              onClick={() => handleSort('email')}
            >
              Email
            </TableHead>
            <TableHead
              className="cursor-pointer text-gray-900 font-semibold"
              onClick={() => handleSort('name')}
            >
              Име
            </TableHead>
            <TableHead
              className="cursor-pointer text-gray-900 font-semibold"
              onClick={() => handleSort('role')}
            >
              Улога
            </TableHead>
            <TableHead
              className="cursor-pointer text-gray-900 font-semibold"
              onClick={() => handleSort('status')}
            >
              Статус
            </TableHead>
            <TableHead
              className="cursor-pointer text-gray-900 font-semibold"
              onClick={() => handleSort('subscription')}
            >
              Претплата
            </TableHead>
            <TableHead className="text-gray-900 font-semibold">Верифициран</TableHead>
            <TableHead
              className="cursor-pointer text-gray-900 font-semibold"
              onClick={() => handleSort('created_at')}
            >
              Креиран
            </TableHead>
            <TableHead className="w-[70px] text-gray-900 font-semibold">Акции</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedUsers.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} className="text-center py-8 text-gray-500">
                Нема корисници
              </TableCell>
            </TableRow>
          ) : (
            sortedUsers.map((user) => (
              <TableRow key={user.id} className="hover:bg-gray-50">
                <TableCell className="font-medium text-gray-900">{user.email}</TableCell>
                <TableCell className="text-gray-700">{user.name}</TableCell>
                <TableCell>{getRoleBadge(user.role)}</TableCell>
                <TableCell>{getStatusBadge(user.status)}</TableCell>
                <TableCell>{getSubscriptionBadge(user.subscription)}</TableCell>
                <TableCell>
                  {user.verified ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
                </TableCell>
                <TableCell className="text-gray-700">
                  {formatDate(user.created_at)}
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

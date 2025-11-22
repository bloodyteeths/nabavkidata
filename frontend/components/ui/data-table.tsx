"use client"

import * as React from "react"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { ChevronUp, ChevronDown, ChevronsUpDown, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

export type SortDirection = "asc" | "desc" | null

export interface ColumnDef<T> {
  id: string
  header: string
  accessorKey?: keyof T
  cell?: (row: T) => React.ReactNode
  sortable?: boolean
  width?: string
}

export interface DataTableProps<T> {
  columns: ColumnDef<T>[]
  data: T[]
  onSort?: (columnId: string, direction: SortDirection) => void
  sortColumn?: string
  sortDirection?: SortDirection
  onPageChange?: (page: number) => void
  totalPages?: number
  currentPage?: number
  isLoading?: boolean
  selectable?: boolean
  selectedRows?: Set<string>
  onRowSelect?: (rowId: string, selected: boolean) => void
  onSelectAll?: (selected: boolean) => void
  getRowId?: (row: T, index: number) => string
  actions?: (row: T) => React.ReactNode
  emptyMessage?: string
  className?: string
}

export function DataTable<T>({
  columns,
  data,
  onSort,
  sortColumn,
  sortDirection,
  onPageChange,
  totalPages = 1,
  currentPage = 1,
  isLoading = false,
  selectable = false,
  selectedRows = new Set(),
  onRowSelect,
  onSelectAll,
  getRowId = (row: T, index: number) => String(index),
  actions,
  emptyMessage = "Нема податоци",
  className,
}: DataTableProps<T>) {
  const handleSort = (columnId: string) => {
    if (!onSort) return

    let newDirection: SortDirection = "asc"
    if (sortColumn === columnId) {
      if (sortDirection === "asc") {
        newDirection = "desc"
      } else if (sortDirection === "desc") {
        newDirection = null
      }
    }
    onSort(columnId, newDirection)
  }

  const handleSelectAll = (checked: boolean) => {
    if (onSelectAll) {
      onSelectAll(checked)
    }
  }

  const handleRowSelect = (rowId: string, checked: boolean) => {
    if (onRowSelect) {
      onRowSelect(rowId, checked)
    }
  }

  const allSelected =
    data.length > 0 && data.every((row, index) => selectedRows.has(getRowId(row, index)))
  const someSelected =
    data.some((row, index) => selectedRows.has(getRowId(row, index))) && !allSelected

  const renderSortIcon = (columnId: string) => {
    if (sortColumn !== columnId) {
      return <ChevronsUpDown className="ml-2 h-4 w-4" />
    }
    if (sortDirection === "asc") {
      return <ChevronUp className="ml-2 h-4 w-4" />
    }
    if (sortDirection === "desc") {
      return <ChevronDown className="ml-2 h-4 w-4" />
    }
    return <ChevronsUpDown className="ml-2 h-4 w-4" />
  }

  const renderPagination = () => {
    if (totalPages <= 1) return null

    const pages: number[] = []
    const maxVisible = 5
    let start = Math.max(1, currentPage - Math.floor(maxVisible / 2))
    let end = Math.min(totalPages, start + maxVisible - 1)

    if (end - start < maxVisible - 1) {
      start = Math.max(1, end - maxVisible + 1)
    }

    for (let i = start; i <= end; i++) {
      pages.push(i)
    }

    return (
      <div className="flex items-center justify-between px-2 py-4">
        <div className="text-sm text-muted-foreground">
          Страна {currentPage} од {totalPages}
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange?.(1)}
            disabled={currentPage === 1 || isLoading}
            aria-label="Прва страна"
          >
            Прва
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange?.(currentPage - 1)}
            disabled={currentPage === 1 || isLoading}
            aria-label="Претходна страна"
          >
            Претходна
          </Button>
          <div className="flex items-center gap-1">
            {start > 1 && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onPageChange?.(1)}
                  disabled={isLoading}
                >
                  1
                </Button>
                {start > 2 && <span className="px-2">...</span>}
              </>
            )}
            {pages.map((page) => (
              <Button
                key={page}
                variant={currentPage === page ? "default" : "outline"}
                size="sm"
                onClick={() => onPageChange?.(page)}
                disabled={isLoading}
                aria-label={`Страна ${page}`}
                aria-current={currentPage === page ? "page" : undefined}
              >
                {page}
              </Button>
            ))}
            {end < totalPages && (
              <>
                {end < totalPages - 1 && <span className="px-2">...</span>}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onPageChange?.(totalPages)}
                  disabled={isLoading}
                >
                  {totalPages}
                </Button>
              </>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange?.(currentPage + 1)}
            disabled={currentPage === totalPages || isLoading}
            aria-label="Следна страна"
          >
            Следна
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange?.(totalPages)}
            disabled={currentPage === totalPages || isLoading}
            aria-label="Последна страна"
          >
            Последна
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("space-y-4", className)}>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {selectable && (
                <TableHead className="w-[50px]">
                  <Checkbox
                    checked={allSelected}
                    onCheckedChange={handleSelectAll}
                    aria-label="Селектирај ги сите редови"
                  />
                </TableHead>
              )}
              {columns.map((column) => (
                <TableHead
                  key={column.id}
                  style={{ width: column.width }}
                  className={cn(column.sortable && "cursor-pointer select-none")}
                >
                  {column.sortable ? (
                    <div
                      className="flex items-center"
                      onClick={() => handleSort(column.id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault()
                          handleSort(column.id)
                        }
                      }}
                      aria-label={`Сортирај по ${column.header}`}
                    >
                      {column.header}
                      {renderSortIcon(column.id)}
                    </div>
                  ) : (
                    column.header
                  )}
                </TableHead>
              ))}
              {actions && <TableHead className="w-[100px]">Акции</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell
                  colSpan={
                    columns.length + (selectable ? 1 : 0) + (actions ? 1 : 0)
                  }
                  className="h-24 text-center"
                >
                  <div className="flex items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">
                      Се вчитува...
                    </span>
                  </div>
                </TableCell>
              </TableRow>
            ) : data.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={
                    columns.length + (selectable ? 1 : 0) + (actions ? 1 : 0)
                  }
                  className="h-24 text-center text-muted-foreground"
                >
                  {emptyMessage}
                </TableCell>
              </TableRow>
            ) : (
              data.map((row, rowIndex) => {
                const rowId = getRowId(row, rowIndex)
                const isSelected = selectedRows.has(rowId)
                return (
                  <TableRow
                    key={rowId}
                    data-state={isSelected ? "selected" : undefined}
                  >
                    {selectable && (
                      <TableCell>
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={(checked) =>
                            handleRowSelect(rowId, checked as boolean)
                          }
                          aria-label={`Селектирај ред ${rowId}`}
                        />
                      </TableCell>
                    )}
                    {columns.map((column) => (
                      <TableCell key={column.id}>
                        {column.cell
                          ? column.cell(row)
                          : column.accessorKey
                            ? String(row[column.accessorKey] ?? "")
                            : ""}
                      </TableCell>
                    ))}
                    {actions && <TableCell>{actions(row)}</TableCell>}
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </div>
      {renderPagination()}
    </div>
  )
}

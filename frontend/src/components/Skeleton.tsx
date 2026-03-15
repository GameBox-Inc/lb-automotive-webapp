import React from 'react'

/** Base block for skeleton placeholders */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-gray-200 dark:bg-gray-700 ${className}`}
      aria-hidden
    />
  )
}

/** Card-shaped skeleton (e.g. metric card, service card) */
export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`rounded-xl border border-gray-200 dark:border-gray-700 p-6 ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <Skeleton className="h-4 w-24 mb-2" />
          <Skeleton className="h-8 w-16" />
        </div>
        <Skeleton className="h-14 w-14 rounded-2xl flex-shrink-0" />
      </div>
      <Skeleton className="h-1 w-full mt-3 rounded-full" />
    </div>
  )
}

/** List row skeleton (e.g. table row or list item) */
export function SkeletonListRow({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center gap-4 py-3 ${className}`}>
      <Skeleton className="h-10 w-10 rounded-lg flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <Skeleton className="h-4 w-3/4 mb-2" />
        <Skeleton className="h-3 w-1/2 max-w-[120px]" />
      </div>
      <Skeleton className="h-6 w-20 rounded-full flex-shrink-0" />
    </div>
  )
}

/** Inline list of skeleton rows */
export function SkeletonList({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }, (_, i) => (
        <SkeletonListRow key={i} />
      ))}
    </div>
  )
}

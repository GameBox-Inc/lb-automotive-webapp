

interface LoadingSpinnerProps {
    size?: 'sm' | 'md' | 'lg'
    className?: string
}

export function LoadingSpinner({ size = 'md', className = '' }: LoadingSpinnerProps) {
    const sizeClasses = {
        sm: 'h-5 w-5 border-2',
        md: 'h-8 w-8 border-b-2',
        lg: 'h-12 w-12 border-t-2 border-b-2'
    }

    return (
        <div className={`animate-spin rounded-full border-lb-red-primary border-r-transparent ${sizeClasses[size]} ${className}`}></div>
    )
}

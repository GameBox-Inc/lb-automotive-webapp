import React, { useState, useMemo } from 'react'
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameDay, startOfWeek, endOfWeek, addMonths, subMonths } from 'date-fns'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface Appointment {
    id: string
    appointment_time: string
    service_type: string
}

interface Service {
    name: string
    duration: number
}

interface AppointmentCalendarProps {
    appointments: Appointment[]
    services: Service[]
    onDateClick?: (date: Date) => void
}

export function AppointmentCalendar({ appointments, services, onDateClick }: AppointmentCalendarProps) {
    const [currentMonth, setCurrentMonth] = useState(new Date())

    const monthStart = startOfMonth(currentMonth)
    const monthEnd = endOfMonth(currentMonth)
    const calendarStart = startOfWeek(monthStart)
    const calendarEnd = endOfWeek(monthEnd)
    const days = eachDayOfInterval({ start: calendarStart, end: calendarEnd })

    // Calculate appointments per day
    const dayData = useMemo(() => {
        const data = new Map<string, { count: number; totalDuration: number }>()

        appointments.forEach(apt => {
            const dateKey = format(new Date(apt.appointment_time), 'yyyy-MM-dd')
            const service = services.find(s => s.name === apt.service_type)
            const duration = service?.duration || 30

            if (!data.has(dateKey)) {
                data.set(dateKey, { count: 0, totalDuration: 0 })
            }
            const current = data.get(dateKey)!
            current.count++
            current.totalDuration += duration
        })

        return data
    }, [appointments, services])

    const getDensityColor = (count: number) => {
        if (count === 0) return 'bg-gray-100 dark:bg-gray-800'
        if (count <= 3) return 'bg-green-100 dark:bg-green-900'
        if (count <= 6) return 'bg-yellow-100 dark:bg-yellow-900'
        return 'bg-red-100 dark:bg-red-900'
    }

    const getDensityTextColor = (count: number) => {
        if (count === 0) return 'text-gray-400 dark:text-gray-600'
        if (count <= 3) return 'text-green-700 dark:text-green-300'
        if (count <= 6) return 'text-yellow-700 dark:text-yellow-300'
        return 'text-red-700 dark:text-red-300'
    }

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            {/* Month Navigation */}
            <div className="flex items-center justify-between mb-6">
                <button
                    onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                >
                    <ChevronLeft className="h-5 w-5" />
                </button>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {format(currentMonth, 'MMMM yyyy')}
                </h3>
                <button
                    onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                >
                    <ChevronRight className="h-5 w-5" />
                </button>
            </div>

            {/* Weekday Headers */}
            <div className="grid grid-cols-7 gap-1 mb-2">
                {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
                    <div key={day} className="text-center text-xs font-semibold text-gray-600 dark:text-gray-400 py-2">
                        {day}
                    </div>
                ))}
            </div>

            {/* Calendar Grid */}
            <div className="grid grid-cols-7 gap-1">
                {days.map(day => {
                    const dateKey = format(day, 'yyyy-MM-dd')
                    const data = dayData.get(dateKey) || { count: 0, totalDuration: 0 }
                    const isCurrentMonth = day.getMonth() === currentMonth.getMonth()
                    const isToday = isSameDay(day, new Date())

                    return (
                        <button
                            key={dateKey}
                            onClick={() => onDateClick?.(day)}
                            className={`
                aspect-square p-2 rounded-lg relative
                ${getDensityColor(data.count)}
                ${isCurrentMonth ? 'opacity-100' : 'opacity-30'}
                ${isToday ? 'ring-2 ring-blue-500' : ''}
                hover:ring-2 hover:ring-gray-400 transition-all
              `}
                        >
                            <div className="text-sm font-medium text-gray-900 dark:text-white">
                                {format(day, 'd')}
                            </div>
                            {data.count > 0 && (
                                <div className={`text-xs font-bold mt-1 ${getDensityTextColor(data.count)}`}>
                                    {data.count}
                                </div>
                            )}
                            {data.totalDuration > 0 && (
                                <div className="text-xs text-gray-600 dark:text-gray-400">
                                    {Math.round(data.totalDuration / 60)}h
                                </div>
                            )}
                        </button>
                    )
                })}
            </div>

            {/* Legend */}
            <div className="mt-6 flex items-center justify-center gap-6 text-xs">
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-green-100 dark:bg-green-900" />
                    <span className="text-gray-600 dark:text-gray-400">Light (1-3)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-yellow-100 dark:bg-yellow-900" />
                    <span className="text-gray-600 dark:text-gray-400">Medium (4-6)</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded bg-red-100 dark:bg-red-900" />
                    <span className="text-gray-600 dark:text-gray-400">Heavy (7+)</span>
                </div>
            </div>
        </div>
    )
}

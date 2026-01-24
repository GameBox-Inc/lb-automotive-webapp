import React, { useMemo } from 'react'
import { format, parseISO, startOfWeek, addDays } from 'date-fns'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

interface Appointment {
    id: string
    appointment_time: string
    service_type: string
}

interface Service {
    name: string
    duration: number
    category?: string
}

interface DurationChartProps {
    appointments: Appointment[]
    services: Service[]
}

export function DurationChart({ appointments, services }: DurationChartProps) {
    const chartData = useMemo(() => {
        // Get current week
        const today = new Date()
        const weekStart = startOfWeek(today)

        // Initialize data for each day of week
        const data: any[] = []
        for (let i = 0; i < 7; i++) {
            const day = addDays(weekStart, i)
            data.push({
                day: format(day, 'EEE'),
                date: format(day, 'yyyy-MM-dd'),
                total: 0
            })
        }

        // Aggregate appointment durations by day
        const serviceCategories = new Set<string>()
        appointments.forEach(apt => {
            const aptDate = format(parseISO(apt.appointment_time), 'yyyy-MM-dd')
            const dayData = data.find(d => d.date === aptDate)

            if (dayData) {
                const service = services.find(s => s.name === apt.service_type)
                const duration = service?.duration || 30
                const category = service?.category || 'Other'

                serviceCategories.add(category)
                dayData[category] = (dayData[category] || 0) + duration / 60 // Convert to hours
                dayData.total += duration / 60
            }
        })

        return { data, categories: Array.from(serviceCategories) }
    }, [appointments, services])

    const colors = [
        '#3b82f6', // blue
        '#10b981', // green
        '#f59e0b', // yellow
        '#ef4444', // red
        '#8b5cf6', // purple
        '#ec4899', // pink
    ]

    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Weekly Capacity (Hours)
            </h3>
            <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData.data} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" label={{ value: 'Hours', position: 'insideBottom', offset: -5 }} />
                    <YAxis dataKey="day" type="category" />
                    <Tooltip
                        formatter={(value: number) => `${value.toFixed(1)}h`}
                        contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: '8px' }}
                    />
                    <Legend />
                    {chartData.categories.map((category, index) => (
                        <Bar
                            key={category}
                            dataKey={category}
                            stackId="a"
                            fill={colors[index % colors.length]}
                        />
                    ))}
                </BarChart>
            </ResponsiveContainer>
        </div>
    )
}

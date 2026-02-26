import React from 'react'
import { Calendar, dateFnsLocalizer, View, Views } from 'react-big-calendar'
import { format, parse, startOfWeek, getDay } from 'date-fns'
import { enUS } from 'date-fns/locale'
import 'react-big-calendar/lib/css/react-big-calendar.css'
import { Appointment, Staff, Service } from '../types'

const locales = {
    'en-US': enUS,
}

const localizer = dateFnsLocalizer({
    format,
    parse,
    startOfWeek,
    getDay,
    locales,
})

interface SmartCalendarProps {
    appointments: Appointment[]
    staff: Staff[]
    services: Service[]
    onSelectEvent: (appointment: Appointment) => void
    onSelectSlot: (slotInfo: { start: Date; end: Date }) => void
}

export const SmartCalendar: React.FC<SmartCalendarProps> = ({
    appointments,
    staff,
    services,
    onSelectEvent,
    onSelectSlot
}) => {
    const [view, setView] = React.useState<View>(Views.WEEK)

    // Transform appointments to calendar events
    const events = appointments.map(apt => {
        const startDate = new Date(apt.appointment_time)

        // Calculate end time based on service duration
        const service = services.find(s => s.name === apt.service_type || s.id === apt.service_type)
        const duration = service ? service.duration : 60 // Default to 60 mins if unknown
        const endDate = new Date(startDate.getTime() + duration * 60000)

        // Determine color based on status
        const statusColorMap: Record<string, string> = {
            pending: '#FDB80E',     // Amber
            confirmed: '#16A34A',   // Green
            in_progress: '#2563EB', // Blue
            completed: '#1F2937',   // Gray
            cancelled: '#EF4444',   // Red
        }

        return {
            id: apt.id,
            title: `${apt.customer_name} - ${apt.service_type}`,
            start: startDate,
            end: endDate,
            resourceId: apt.assigned_staff_id, // For potential resource view
            data: apt,
            status: apt.status,
            color: statusColorMap[apt.status] || '#9CA3AF'
        }
    })

    const eventStyleGetter = (event: any) => {
        return {
            style: {
                backgroundColor: event.color,
                borderRadius: '4px',
                opacity: 0.9,
                color: 'white',
                border: '0px',
                display: 'block'
            }
        }
    }

    return (
        <div className="h-[600px] bg-white dark:bg-gray-800 rounded-lg shadow-md p-4">
            <Calendar
                localizer={localizer}
                events={events}
                startAccessor="start"
                endAccessor="end"
                style={{ height: '100%' }}
                view={view}
                onView={setView}
                views={[Views.MONTH, Views.WEEK, Views.DAY, Views.AGENDA]}
                min={new Date(0, 0, 0, 7, 0, 0)} // Start at 7 AM
                max={new Date(0, 0, 0, 19, 0, 0)} // End at 7 PM
                step={30}
                timeslots={2}
                selectable
                onSelectEvent={(event) => onSelectEvent(event.data)}
                onSelectSlot={onSelectSlot}
                eventPropGetter={eventStyleGetter}
                tooltipAccessor={(event) => `${event.title} (${event.status})`}
            />
        </div>
    )
}

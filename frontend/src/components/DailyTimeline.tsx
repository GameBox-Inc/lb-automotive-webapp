import React from 'react';
import { format } from 'date-fns';
import { Appointment, Service } from '../lib/supabase';
import { User, Clock, ExternalLink } from 'lucide-react';
import { EmptyState } from './EmptyState';

interface DailyTimelineProps {
    appointments: Appointment[];
    services: Service[];
    /** If provided, show this day's schedule; otherwise show today. */
    selectedDate?: Date;
    /** When provided, appointment blocks and rows are clickable and open repair/case details. */
    onAppointmentClick?: (appointment: Appointment) => void;
}

export const DailyTimeline: React.FC<DailyTimelineProps> = ({ appointments, services, selectedDate, onAppointmentClick }) => {
    // Config: Shop hours 8:00 to 18:00
    const START_HOUR = 8;
    const END_HOUR = 18;
    const TOTAL_MINUTES = (END_HOUR - START_HOUR) * 60;

    const displayDate = selectedDate ?? new Date();
    const displayDateString = displayDate.toDateString();

    // Filter for the selected day (or today) and sort by time
    const todaysAppointments = appointments
        .filter(a => new Date(a.appointment_time).toDateString() === displayDateString)
        .sort((a, b) => new Date(a.appointment_time).getTime() - new Date(b.appointment_time).getTime());

    const getServiceDuration = (serviceName: string) => {
        const service = services.find(s => s.name === serviceName);
        return service ? service.duration : 60; // Default 60 min
    };

    const getPosition = (timeString: string, duration: number) => {
        const date = new Date(timeString);
        const hours = date.getHours();
        const minutes = date.getMinutes();

        // Calculate minutes from start of day (8:00)
        const minutesFromStart = (hours * 60 + minutes) - (START_HOUR * 60);

        // Cap at graphical bounds
        const startPercent = Math.max(0, (minutesFromStart / TOTAL_MINUTES) * 100);
        const widthPercent = Math.min(100 - startPercent, (duration / TOTAL_MINUTES) * 100);

        return { left: `${startPercent}%`, width: `${widthPercent}%` };
    };

    const statusColors: Record<string, string> = {
        pending: 'bg-yellow-500',
        confirmed: 'bg-green-500',
        in_progress: 'bg-lb-red-primary',
        completed: 'bg-gray-600',
        cancelled: 'bg-red-500',
    };

    const isToday = displayDateString === new Date().toDateString();
    const emptyTitle = isToday ? 'No Appointments Today' : `No Appointments on ${format(displayDate, 'MMM d, yyyy')}`;

    if (todaysAppointments.length === 0) {
        return (
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-8 border border-gray-100 dark:border-gray-700">
                <EmptyState
                    icon={<Clock className="h-7 w-7" />}
                    title={emptyTitle}
                    description="The schedule is clear for the day."
                />
            </div>
        );
    }

    return (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 overflow-hidden">
            <div className="p-6 border-b border-gray-100 dark:border-gray-700">
                <h2 className="text-lg font-bold text-gray-900 dark:text-white">{isToday ? "Today's Schedule" : 'Schedule'}</h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">{format(displayDate, 'EEEE, MMMM do, yyyy')}</p>
            </div>

            <div className="p-6 overflow-x-auto">
                <div className="min-w-[600px]">
                    {/* Time Header - same two-column layout as rows so labels align with bars */}
                    <div className="flex mb-4 relative h-6 text-xs text-gray-400 font-mono">
                        <div className="w-48 flex-shrink-0 pr-4" aria-hidden="true" />
                        <div className="flex-grow relative h-full">
                            {[8, 10, 12, 14, 16, 18].map(hour => {
                                const left = ((hour - START_HOUR) / (END_HOUR - START_HOUR)) * 100;
                                return (
                                    <div key={hour} className="absolute transform -translate-x-1/2" style={{ left: `${left}%` }}>
                                        {hour > 12 ? `${hour - 12} PM` : hour === 12 ? '12 PM' : `${hour} AM`}
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Grid Rows */}
                    <div className="space-y-3">
                        {todaysAppointments.map(apt => {
                            const duration = getServiceDuration(apt.service_type);
                            const { left, width } = getPosition(apt.appointment_time, duration);
                            const isClickable = !!onAppointmentClick;

                            const handleClick = () => {
                                if (onAppointmentClick) onAppointmentClick(apt);
                            };

                            return (
                                <div
                                    key={apt.id}
                                    className={`relative h-12 flex items-center group ${isClickable ? 'cursor-pointer' : ''}`}
                                    onClick={isClickable ? handleClick : undefined}
                                    onKeyDown={isClickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleClick(); } } : undefined}
                                    role={isClickable ? 'button' : undefined}
                                    tabIndex={isClickable ? 0 : undefined}
                                    title={isClickable ? `View repair details for ${apt.customer_name} – ${apt.service_type}` : undefined}
                                >
                                    {/* Row Background Lines */}
                                    <div className="absolute inset-x-0 h-full border-b border-gray-50 dark:border-gray-700/50 -z-10" />

                                    {/* Y-Axis Label (Appointment/Customer) */}
                                    <div className="w-48 flex-shrink-0 pr-4 flex items-center gap-2">
                                        <div className="h-8 w-8 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center flex-shrink-0 text-gray-500">
                                            <User size={14} />
                                        </div>
                                        <div className="truncate">
                                            <p className="text-sm font-medium text-gray-900 dark:text-white truncate" title={apt.customer_name}>
                                                {apt.customer_name}
                                            </p>
                                            <p className="text-xs text-gray-500 truncate">{format(new Date(apt.appointment_time), 'h:mm a')}</p>
                                        </div>
                                        {isClickable && (
                                            <ExternalLink className="h-3.5 w-3.5 text-gray-400 shrink-0 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" aria-hidden />
                                        )}
                                    </div>

                                    {/* Timeline Bar Area */}
                                    <div className="flex-grow relative h-full bg-gray-50/50 dark:bg-gray-900/30 rounded-lg">
                                        {/* Vertical Grid Lines */}
                                        {[8, 10, 12, 14, 16, 18].map((hour) => (
                                            <div
                                                key={hour}
                                                className="absolute top-0 bottom-0 border-r border-dashed border-gray-200 dark:border-gray-700"
                                                style={{ left: `${((hour - START_HOUR) / (END_HOUR - START_HOUR)) * 100}%` }}
                                            />
                                        ))}

                                        {/* The Bar */}
                                        <div
                                            className={`absolute top-1/2 -translate-y-1/2 h-8 rounded-md shadow-sm border border-white/10 ${statusColors[apt.status] || 'bg-blue-500'} transition-all hover:scale-[1.02] ${isClickable ? 'cursor-pointer hover:ring-2 hover:ring-offset-1 hover:ring-white/50' : ''} group-hover:shadow-md`}
                                            style={{ left, width }}
                                            title={isClickable ? `View repair details – ${apt.service_type} (${duration} mins)` : `${apt.service_type} (${duration} mins)`}
                                            onClick={isClickable ? (e) => { e.stopPropagation(); handleClick(); } : undefined}
                                        >
                                            <div className="px-2 h-full flex items-center justify-between text-xs text-white font-medium overflow-hidden">
                                                <span className="truncate mr-1 drop-shadow-md">{apt.service_type}</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
};

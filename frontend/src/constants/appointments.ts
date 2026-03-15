/** Appointment statuses considered "active" (excludes completed and cancelled). */
export const ACTIVE_APPOINTMENT_STATUSES = ['pending', 'confirmed', 'in_progress'] as const

export function isActiveAppointmentStatus(status: string): boolean {
  return ACTIVE_APPOINTMENT_STATUSES.includes(status as (typeof ACTIVE_APPOINTMENT_STATUSES)[number])
}

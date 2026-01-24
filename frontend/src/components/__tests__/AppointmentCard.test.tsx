import { render, screen } from '@testing-library/react';
import { AppointmentCard } from '../AppointmentCard';
import { describe, it, expect, vi } from 'vitest';

// Mock lucide-react icons since they might cause issues in JSDOM if not handled (though usually fine)
vi.mock('lucide-react', async (importOriginal) => {
    const actual = await importOriginal();
    return {
        ...actual as any,
        // Add specific mocks if needed, otherwise actual implementation is often fine for SVGs
    };
});

// Mock api client to avoid network calls
vi.mock('../../lib/supabase', () => ({
    apiClient: {
        updateAppointmentStatus: vi.fn(),
        logError: vi.fn(),
    },
}));

describe('AppointmentCard', () => {
    const mockAppointment = {
        id: '1',
        customer_name: 'John Doe',
        phone_number: '555-0123',
        appointment_time: '2024-01-01T10:00:00Z',
        service_type: 'Oil Change',
        status: 'pending',
    };

    const mockServices = [
        { name: 'Oil Change', description: 'Standard oil change', duration: 30, price: 50 },
    ];

    it('renders customer name and service type', () => {
        render(
            <AppointmentCard
                appointment={mockAppointment}
                onUpdate={() => { }}
                services={mockServices}
            />
        );

        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('Oil Change')).toBeInTheDocument();
    });

    it('displays the correct status', () => {
        render(
            <AppointmentCard
                appointment={mockAppointment}
                onUpdate={() => { }}
                services={mockServices}
            />
        );

        // Pending status usually renders a styled badge
        expect(screen.getByText('Pending')).toBeInTheDocument();
    });

    it('shows verify button when status is pending', () => {
        render(
            <AppointmentCard
                appointment={mockAppointment}
                onUpdate={() => { }}
                services={mockServices}
            />
        );

        expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument();
    });
});

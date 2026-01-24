import React, { useState, useEffect } from 'react'
import { Phone, CheckCircle, ChevronRight } from 'lucide-react'
import { apiClient, Service, Customer } from '../lib/supabase'
import { formatCurrency } from '../utils/format'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

export default function CheckIn() {
    const navigate = useNavigate()
    const [step, setStep] = useState<'phone' | 'confirm' | 'services' | 'success'>('phone')
    const [phoneNumber, setPhoneNumber] = useState('')
    const [loading, setLoading] = useState(false)
    const [customer, setCustomer] = useState<Customer | null>(null)
    const [services, setServices] = useState<Service[]>([])
    const [customerName, setCustomerName] = useState('')
    const [showExitPrompt, setShowExitPrompt] = useState(false)
    const [exitClickCount, setExitClickCount] = useState(0)

    // Request fullscreen on mount
    useEffect(() => {
        const enterFullscreen = async () => {
            try {
                if (document.documentElement.requestFullscreen) {
                    await document.documentElement.requestFullscreen()
                }
            } catch (err) {
                console.log('Fullscreen not supported or denied')
            }
        }
        enterFullscreen()

        return () => {
            if (document.fullscreenElement) {
                document.exitFullscreen().catch(() => { })
            }
        }
    }, [])

    // Hidden exit mechanism - click logo 5 times
    const handleLogoClick = () => {
        const newCount = exitClickCount + 1
        setExitClickCount(newCount)

        if (newCount >= 5) {
            setShowExitPrompt(true)
            setExitClickCount(0)
        }

        // Reset counter after 3 seconds
        setTimeout(() => setExitClickCount(0), 3000)
    }

    const handleExitKiosk = () => {
        if (document.fullscreenElement) {
            document.exitFullscreen().catch(() => { })
        }
        navigate('/')
    }

    const handlePhoneSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setLoading(true)
        try {
            // Clean phone number
            const cleanPhone = phoneNumber.replace(/\D/g, '')

            // Search for customer
            const foundCustomer = await apiClient.searchCustomerByPhone(cleanPhone)

            if (foundCustomer) {
                setCustomer(foundCustomer)
                setStep('confirm')
            } else {
                setStep('confirm') // New customer flow
            }
        } catch (error) {
            console.error('Error searching customer:', error)
            toast.error('Error searching for customer')
        } finally {
            setLoading(false)
        }
    }

    const handleConfirm = async () => {
        setLoading(true)
        try {
            if (!customer) {
                // Create new customer
                const newCustomer = await apiClient.createCustomer({
                    name: customerName,
                    phone: phoneNumber.replace(/\D/g, ''),
                    email: '' // Optional for kiosk
                })
                setCustomer(newCustomer)
            }

            // Fetch services for selection
            const servicesData = await apiClient.getServices()
            setServices(servicesData)
            setStep('services')
        } catch (error) {
            console.error('Error creating customer:', error)
            toast.error('Error processing information')
        } finally {
            setLoading(false)
        }
    }

    const handleServiceSelect = async (service: Service) => {
        setLoading(true)
        try {
            if (!customer) return

            // Create appointment (Walk-in)
            await apiClient.createAppointment({
                customer_id: customer.id,
                service_id: service.id,
                appointment_time: new Date().toISOString(),
                vehicle_make: 'Unknown', // Kiosk simplified
                vehicle_model: 'Unknown',
                vehicle_year: new Date().getFullYear(),
                notes: 'Kiosk Walk-in',
                // Required fields for interface
                customer_name: customer.name,
                phone_number: customer.phone,
                service_type: service.name,
                emergency_request: false
            })

            setStep('success')
            // Reset after delay
            setTimeout(() => {
                setStep('phone')
                setPhoneNumber('')
                setCustomer(null)
                setCustomerName('')
            }, 5000)
        } catch (error) {
            console.error('Error creating appointment:', error)
            toast.error('Failed to create appointment')
        } finally {
            setLoading(false)
        }
    }

    if (loading) return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
            <LoadingSpinner size="lg" />
        </div>
    )

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-4 relative">
            {/* Exit Prompt Modal */}
            {showExitPrompt && (
                <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
                    <div className="bg-white rounded-lg p-8 max-w-md">
                        <h3 className="text-xl font-bold text-gray-900 mb-4">Exit Kiosk Mode?</h3>
                        <p className="text-gray-600 mb-6">This will return to the admin dashboard.</p>
                        <div className="flex gap-4">
                            <button
                                onClick={() => setShowExitPrompt(false)}
                                className="flex-1 px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleExitKiosk}
                                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                            >
                                Exit Kiosk
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl overflow-hidden">
                <div
                    className="bg-[#B91C1C] p-6 text-white text-center cursor-pointer select-none"
                    onClick={handleLogoClick}
                >
                    <h1 className="text-3xl font-bold font-heading">LB AUTO REPAIR</h1>
                    <p className="text-white/80 mt-2">Self Check-in Kiosk</p>
                </div>

                <div className="p-8">
                    {step === 'phone' && (
                        <div className="space-y-6">
                            <div className="text-center">
                                <h2 className="text-2xl font-semibold text-gray-900">Welcome!</h2>
                                <p className="text-gray-500 mt-2">Please enter your phone number to begin</p>
                            </div>

                            <form onSubmit={handlePhoneSubmit} className="space-y-6">
                                <div>
                                    <label htmlFor="phone" className="sr-only">Phone Number</label>
                                    <div className="relative">
                                        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                                            <Phone className="h-6 w-6 text-gray-400" />
                                        </div>
                                        <input
                                            type="tel"
                                            id="phone"
                                            required
                                            className="block w-full pl-12 pr-4 py-4 text-2xl border-gray-300 rounded-lg focus:ring-red-500 focus:border-red-500 text-center tracking-widest"
                                            placeholder="(555) 555-5555"
                                            value={phoneNumber}
                                            onChange={(e) => setPhoneNumber(e.target.value)}
                                        />
                                    </div>
                                </div>
                                <button
                                    type="submit"
                                    disabled={phoneNumber.length < 10}
                                    className="w-full flex items-center justify-center py-4 px-4 border border-transparent rounded-lg shadow-sm text-xl font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                >
                                    Continue
                                    <ChevronRight className="ml-2 h-6 w-6" />
                                </button>
                            </form>
                        </div>
                    )}

                    {step === 'confirm' && (
                        <div className="space-y-6">
                            <div className="text-center">
                                <h2 className="text-2xl font-semibold text-gray-900">
                                    {customer ? `Welcome back, ${customer.name}!` : "Let's get your details"}
                                </h2>
                                <p className="text-gray-500 mt-2">
                                    {customer ? 'Is this you?' : 'Please enter your name'}
                                </p>
                            </div>

                            {!customer && (
                                <div>
                                    <label className="block text-sm font-medium text-gray-700">Full Name</label>
                                    <div className="mt-1">
                                        <input
                                            type="text"
                                            required
                                            className="block w-full border-gray-300 rounded-md shadow-sm focus:ring-red-500 focus:border-red-500 sm:text-lg p-3"
                                            value={customerName}
                                            onChange={(e) => setCustomerName(e.target.value)}
                                        />
                                    </div>
                                </div>
                            )}

                            <button
                                onClick={handleConfirm}
                                className="w-full flex items-center justify-center py-4 px-4 border border-transparent rounded-lg shadow-sm text-xl font-medium text-white bg-red-600 hover:bg-red-700 transition-colors"
                            >
                                {customer ? 'Yes, Check In' : 'Continue'}
                            </button>

                            <button
                                onClick={() => {
                                    setCustomer(null)
                                    setStep('phone')
                                }}
                                className="w-full py-3 text-gray-500 hover:text-gray-700"
                            >
                                Back
                            </button>
                        </div>
                    )}

                    {step === 'services' && (
                        <div className="space-y-6">
                            <div className="text-center">
                                <h2 className="text-2xl font-semibold text-gray-900">Select Service</h2>
                                <p className="text-gray-500 mt-2">What brings you in today?</p>
                            </div>

                            <div className="grid grid-cols-1 gap-4 max-h-[400px] overflow-y-auto">
                                {services.map((service) => (
                                    <button
                                        key={service.id}
                                        onClick={() => handleServiceSelect(service)}
                                        className="flex flex-col items-start p-4 border-2 border-gray-200 rounded-xl hover:border-red-500 hover:bg-red-50 transition-all text-left"
                                    >
                                        <span className="text-lg font-medium text-gray-900">{service.name}</span>
                                        <span className="text-gray-500">{service.duration} mins • {formatCurrency(service.price)}</span>
                                    </button>
                                ))}
                            </div>

                            <button
                                onClick={() => setStep('confirm')}
                                className="w-full py-3 text-gray-500 hover:text-gray-700"
                            >
                                Back
                            </button>
                        </div>
                    )}

                    {step === 'success' && (
                        <div className="text-center space-y-6 py-8">
                            <div className="mx-auto flex items-center justify-center h-24 w-24 rounded-full bg-green-100">
                                <CheckCircle className="h-12 w-12 text-green-600" />
                            </div>
                            <div>
                                <h2 className="text-3xl font-bold text-gray-900">You're Checked In!</h2>
                                <p className="text-gray-500 mt-2">Please take a seat, we'll be with you shortly.</p>
                            </div>
                            <p className="text-sm text-gray-400">Resetting in 5 seconds...</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}

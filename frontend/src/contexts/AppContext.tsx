import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient } from '../lib/supabase';
import { Service, Staff } from '../types';

interface AppContextType {
    services: Service[];
    staff: Staff[];
    isLoading: boolean;
    refreshData: () => Promise<void>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [services, setServices] = useState<Service[]>([]);
    const [staff, setStaff] = useState<Staff[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const fetchData = async () => {
        // Only fetch if user is authenticated
        if (!apiClient.isAuthenticated()) {
            setIsLoading(false);
            return;
        }

        try {
            const [servicesData, staffData] = await Promise.all([
                apiClient.getServices(),
                apiClient.getStaff()
            ]);
            setServices(servicesData);
            setStaff(staffData);
        } catch (error) {
            console.error('Error fetching global data:', error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    return (
        <AppContext.Provider value={{ services, staff, isLoading, refreshData: fetchData }}>
            {children}
        </AppContext.Provider>
    );
};

export const useAppContext = () => {
    const context = useContext(AppContext);
    if (context === undefined) {
        throw new Error('useAppContext must be used within an AppProvider');
    }
    return context;
};

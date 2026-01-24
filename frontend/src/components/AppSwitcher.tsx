import React from 'react';
import { LayoutDashboard, Calendar, PenTool, Wrench, CheckSquare, Users, Settings, Phone } from 'lucide-react';
import { Link } from 'react-router-dom';

interface AppSwitcherProps {
    onClose?: () => void;
    isAdmin?: boolean;
}

const AppModule = ({ to, icon: Icon, label, color, onClose }: { to: string, icon: any, label: string, color: string, onClose?: () => void }) => (
    <Link
        to={to}
        onClick={onClose}
        className="flex flex-col items-center p-3 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-all duration-200 group border border-transparent hover:border-gray-200 dark:hover:border-gray-600 min-h-[110px] h-auto"
    >
        <div className={`p-3 rounded-lg mb-2 transition-transform group-hover:scale-110 ${color} shadow-sm shrink-0`}>
            <Icon className="w-6 h-6 text-white" />
        </div>
        <span className="text-sm font-medium text-gray-700 dark:text-gray-200 text-center leading-tight line-clamp-2 h-10 flex items-center justify-center">
            {label}
        </span>
    </Link>
);

export const AppSwitcher: React.FC<AppSwitcherProps> = ({ onClose, isAdmin }) => {
    return (
        <div className="p-4 grid grid-cols-3 gap-2 min-w-[320px]">
            <AppModule
                to="/"
                icon={LayoutDashboard}
                label="Dashboard"
                color="bg-blue-600"
                onClose={onClose}
            />
            <AppModule
                to="/appointments"
                icon={Calendar}
                label="Calendar"
                color="bg-purple-600"
                onClose={onClose}
            />
            <AppModule
                to="/repairs"
                icon={Wrench}
                label="My Repairs"
                color="bg-emerald-600"
                onClose={onClose}
            />
            <AppModule
                to="/services"
                icon={PenTool}
                label="Services"
                color="bg-amber-500"
                onClose={onClose}
            />
            <AppModule
                to="/settings"
                icon={Settings}
                label="Settings"
                color="bg-gray-600"
                onClose={onClose}
            />

            {isAdmin && (
                <>
                    <div className="col-span-3 my-2 border-t border-gray-100 dark:border-gray-700" />
                    <AppModule
                        to="/checkin"
                        icon={CheckSquare}
                        label="Kiosk"
                        color="bg-indigo-600"
                        onClose={onClose}
                    />
                    <AppModule
                        to="/admin/staff"
                        icon={Users}
                        label="Staff"
                        color="bg-rose-600"
                        onClose={onClose}
                    />
                    <AppModule
                        to="/admin/ivr"
                        icon={Phone}
                        label="IVR"
                        color="bg-pink-600"
                        onClose={onClose}
                    />
                </>
            )}
        </div>
    );
};

export default AppSwitcher

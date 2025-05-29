-- Insert sample services
INSERT INTO services (name, description, duration, price, category, is_emergency)
VALUES
    ('Oil Change', 'Standard oil change and filter replacement', 60, 49.99, 'Maintenance', false),
    ('Tire Rotation', 'Rotate all four tires to ensure even wear', 30, 29.99, 'Maintenance', false),
    ('Brake Inspection', 'Comprehensive brake system inspection', 45, 39.99, 'Safety', false),
    ('Emergency Roadside Assistance', '24/7 roadside assistance', 15, 99.99, 'Emergency', true),
    ('Flat Tire Repair', 'Flat tire repair or replacement', 30, 49.99, 'Emergency', true),
    ('Battery Replacement', 'Car battery replacement', 45, 79.99, 'Emergency', true);

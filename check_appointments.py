import sqlite3

conn = sqlite3.connect('python-backend/data/lb_automotive.db')
c = conn.cursor()
c.execute('SELECT customer_name, phone_number, service_type, appointment_time, status, emergency_request FROM appointments ORDER BY created_at DESC LIMIT 5')
print('Recent appointments:')
for row in c.fetchall():
    print(f'  Customer: {row[0]}, Phone: {row[1]}, Service: {row[2]}')
    print(f'    Time: {row[3]}, Status: {row[4]}, Emergency: {row[5]}')
    print()
conn.close()

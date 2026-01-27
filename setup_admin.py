from database import init_db, create_user

print("=== Wrestling Brackets - Admin Setup ===\n")

init_db()

username = input("Enter admin username: ")
password = input("Enter admin password: ")
confirm = input("Confirm password: ")

if password != confirm:
    print("Passwords don't match!")
    exit(1)

if len(password) < 6:
    print("Password must be at least 6 characters!")
    exit(1)

if create_user(username, password):
    print(f"\n✓ Admin user '{username}' created successfully!")
else:
    print(f"\n✗ Username '{username}' already exists.")
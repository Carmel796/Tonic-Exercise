import random, string

TECHNOLOGY_TEMPLATES = {
    "database": [
        "Database {db_name} on {server} is experiencing slow query performance",
        "{server} PostgreSQL connection pool exhausted",
        "MySQL replication lag on {server} exceeds 10 seconds",
        "Oracle backup failed on {server} - tablespace full",
        "{server} MongoDB replica set member unreachable"
    ],
    "networking": [
        "Network connectivity issues between {server} and {server2}",
        "{server} experiencing packet loss to gateway",
        "VPN tunnel down affecting {server}",
        "Firewall blocking port 443 on {server}",
        "{server} DNS resolution failures"
    ],
    "authentication": [
        "LDAP authentication failing on {server}",
        "Users unable to login to {server} - Active Directory timeout",
        "{server} Kerberos ticket expiration issues",
        "SSO integration broken on {server}",
        "Failed login attempts from {server} exceed threshold"
    ],
    "api": [
        "{server} REST API returning 500 errors",
        "API rate limiting triggered on {server}",
        "{server} GraphQL endpoint timeout",
        "Webhook delivery failures from {server}",
        "{server} API gateway health check failing"
    ],
    "storage": [
        "Disk space critically low on {server} - 95% full",
        "{server} NFS mount unresponsive",
        "S3 bucket access denied from {server}",
        "{server} RAID array degraded - drive failure",
        "Backup volume on {server} out of space"
    ]
}

PREFIX_VARIANTS = ["srv", "SRV", "Srv", "sRv", "srV", "SRv", "SrV", "sRV"]

def generate_server_pool(size=200): #unless exact server name eas generated
    servers = set()
    chars = string.ascii_lowercase + string.digits  # a-zA-Z0-9
    for _ in range(size):
        suffix_length = random.randint(2, 10)
        suffix = ''.join(random.choices(chars, k=suffix_length))
        servers.add(f"{suffix}")
    return servers

SERVER_POOL = list(generate_server_pool(200))

def random_server_name():
    prefix = random.choice(PREFIX_VARIANTS)
    # 90% of the time, pick from the pool (existing server)
    if random.random() < 0.9:
        suffix = random.choice(SERVER_POOL)
        return f"{prefix}-{suffix}"
    # 10% new random/invalid server (to simulate noise)
    length = random.randint(2, 10)
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{prefix}-{suffix}"

def generate_description():
    tech = random.choice(list(TECHNOLOGY_TEMPLATES.keys()))
    template = random.choice(TECHNOLOGY_TEMPLATES[tech])
    text = template.format(
        server=random_server_name(),
        server2=random_server_name(),
        db_name=random.choice(["customers", "orders", "analytics", "inventory"])
    )
    # Random chance of no valid server or garbage text
    if random.random() < 0.05:
        text = text.replace("srv-", "xyz-")
    if random.random() < 0.05:
        text = text.replace(random_server_name(), "")
    return tech, text
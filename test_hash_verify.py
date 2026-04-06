import hashlib

key = 'Y4PFDwi'
txnid = 'SUB00034-26040516262'
amount = '3000.00'
productinfo = 'ITR'
firstname = 'boopath'
email = 'prakash.venkatesan@alonioncapital.com'
udf1 = 'ITR-SUB-00034'
salt = 'eKoE70FdIdqSFc0sgo0TouPKj68x9ee8'
expected = 'eb447f4dccdc9bbee3f6a66b273b9176522ca1a6b4f8bf4d52651c77ec3d83992762e5c0cb106591f9506d238b1cf351837590a5688c1854f87eed4928170e41'

base = f'{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|{udf1}'

print("Testing all possible pipe counts after udf1 before SALT:\n")
for pipes in range(1, 15):
    pipe_str = '|' * pipes
    full_str = base + pipe_str + salt
    h = hashlib.sha512(full_str.encode('utf-8')).hexdigest()
    match = '<<< MATCH!' if h.lower() == expected.lower() else ''
    print(f"{pipes:2d} pipes: {h[:30]}... {match}")

print(f"\nExpected: {expected}")

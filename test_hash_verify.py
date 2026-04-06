import hashlib

# CONFIRMED CREDENTIALS from PayU Dashboard
key = 'Y4PFDw'
salt = 'eKoE70FdIdqSFc0sgo0TouPKj68x9ee8'

# Values from PayU error page (ITR-SUB-00021 transaction)
txnid = 'SUB00021-260406120541'
amount = '1000.00'
productinfo = 'ITR'
firstname = 'Ashwin kumar'
email = 'ashiwnkumark59@gmail.com'
udf1 = 'ITR-SUB-00021'

# PayU's expected v1 hash from the error page  
payu_expected = "8ac4175594cd97a5abe9c109f79ddee2424e9a70ce3ccf8995061e82defb4d29626d7f34449339bc8db0ccf13f7900689d7d7299e3a778a3ac08b48253535ad"

base = f'{key}|{txnid}|{amount}|{productinfo}|{firstname}|{email}|{udf1}'

print("=== Testing all pipe counts after udf1 ===")
for pipes in range(6, 16):
    segments = [key, txnid, amount, productinfo, firstname, email, udf1]
    segments += [''] * (pipes - 6)  # add empty udf fields
    segments.append(salt)
    hash_str = '|'.join(segments)
    h = hashlib.sha512(hash_str.encode('utf-8')).hexdigest()
    match = '<<< MATCH!' if h.lower() == payu_expected.lower() else ''
    total_pipes = len(segments) - 1
    print(f"  {total_pipes} total pipes: {h[:30]}... {match}")

print()
print(f"PayU expected:  {payu_expected[:30]}...")

# Also try with alternate salt variants
print("\n=== Testing salt variants (l vs I) ===")
salt_variants = [
    ('Original (capital I)', 'eKoE70FdIdqSFc0sgo0TouPKj68x9ee8'),
    ('Lowercase l',          'eKoE70FdldqSFc0sgo0TouPKj68x9ee8'),
]
for label, s in salt_variants:
    segments = [key, txnid, amount, productinfo, firstname, email, udf1, '', '', '', '', '', '', '', '', s]
    h15 = hashlib.sha512('|'.join(segments[:16]).encode()).hexdigest()
    segments2 = [key, txnid, amount, productinfo, firstname, email, udf1, '', '', '', '', '', '', '', s]
    h14 = hashlib.sha512('|'.join(segments2[:15]).encode()).hexdigest()
    match15 = '<<< MATCH (15p)!' if h15.lower() == payu_expected.lower() else ''
    match14 = '<<< MATCH (14p)!' if h14.lower() == payu_expected.lower() else ''
    print(f"  {label}: 15p={h15[:20]}...{match15}  14p={h14[:20]}...{match14}")

# Try with amount without decimals
print("\n=== Testing amount variants ===")
for amt in ['1000', '1000.0', '1000.00']:
    segments = [key, txnid, amt, productinfo, firstname, email, udf1, '', '', '', '', '', '', '', '', salt]
    for total_pipes in [14, 15, 16]:
        segs = [key, txnid, amt, productinfo, firstname, email, udf1]
        segs += [''] * (total_pipes - 6)
        segs.append(salt)
        h = hashlib.sha512('|'.join(segs).encode()).hexdigest()
        match = '<<< MATCH!' if h.lower() == payu_expected.lower() else ''
        if match:
            print(f"  amount={amt}, pipes={total_pipes}: MATCH! {h[:30]}")

import hashlib

# Values from CURRENT PayU error (ITR-SUB-00045, puneethi, 3000.00)
key = 'Y4PFDw'
txnid = 'SUB00045-260406130339'
amount = '3000.00'
productinfo = 'ITR'
firstname = 'puneethi'
email = 'puneethi@gmail.com'
udf1 = 'ITR-SUB-00045'

# PayU expected hash from current error page
payu_expected = "e45c9d6f42aec94da2634627dccb5c8f0a55125d799bea50606d2209ee5bc2e1290883637e8153686818d5c0f8f5e81b2b238cd72669ab4750994004ac342ac4"

salt_I = 'eKoE70FdIdqSFc0sgo0TouPKj68x9ee8'  # capital I
salt_l = 'eKoE70FdldqSFc0sgo0TouPKj68x9ee8'  # lowercase l

print("Testing CURRENT transaction (ITR-SUB-00045, 3000.00):")
print(f"PayU expected: {payu_expected[:30]}...")
print()

for label, salt in [('Capital I', salt_I), ('Lowercase l', salt_l)]:
    for total_pipes in [14, 15, 16, 17]:
        empty_count = total_pipes - 6  # pipes after email = udf fields + salt
        segments = [key, txnid, amount, productinfo, firstname, email, udf1]
        segments += [''] * (empty_count - 1)  # udf2..udfN all empty
        segments.append(salt)
        h = hashlib.sha512('|'.join(segments).encode('utf-8')).hexdigest()
        match = '  <<< MATCH!' if h.lower() == payu_expected.lower() else ''
        print(f"  {label} + {total_pipes} pipes: {h[:30]}...{match}")
    print()

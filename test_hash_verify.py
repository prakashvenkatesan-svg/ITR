import hashlib

key = 'Y4PFDw'
txnid = 'SUB00044-260406145238'
amount = '2000.00'
productinfo = 'ITR'
firstname = 'dravid'
email = 'prakashv7528@gmail.com'
udf1 = 'ITR-SUB-00044'
salt_I = 'eKoE70FdIdqSFc0sgo0TouPKj68x9ee8'
salt_l = 'eKoE70FdldqSFc0sgo0TouPKj68x9ee8'

expected_hash = "620db59ac74d12e8b3124ae45e50e6177e30b5a7255f104ddfc3aede6a4b3ded7927a8a8d39c5b3404bca2d663edb28aa77921ca83e3967ac586e0b823b3d43"
our_hash = "f0286fe2a4226146ed4aa454f67711fd489dc37cce12b9c23e035f1a7916b4e81153f7bd2a0a3fd6b948fec9aeb9b5daca74bbcfc365fc162318f984ee82aea"

print("Trying variations to find expected_hash and our_hash...")

for salt_name, salt in [('capital I', salt_I), ('lowercase l', salt_l)]:
    for pipes in range(10, 20):
        # Build segments
        segments = [key, txnid, amount, productinfo, firstname, email, udf1]
        empty_count = pipes - 6
        segments.extend([""] * empty_count)
        segments.append(salt)
        
        hash_str = "|".join(segments)
        h = hashlib.sha512(hash_str.encode('utf-8')).hexdigest()
        
        if h == expected_hash:
            print(f"FOUND expected_hash! Salt: {salt_name}, Pipes: {pipes}, Hash Input: {hash_str}")
        if h == our_hash:
            print(f"FOUND our_hash! Salt: {salt_name}, Pipes: {pipes}, Hash Input: {hash_str}")

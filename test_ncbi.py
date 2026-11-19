import requests, time

url = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
total = 0
start = time.time()

with requests.get(url, stream=True, timeout=(15, 30)) as r:
    r.raise_for_status()
    for chunk in r.iter_content(1024 * 1024):
        total += len(chunk)
        elapsed = time.time() - start
        print(f"{total / 1048576:.0f} MB | {elapsed:.1f} sec | {total / 1048576 / elapsed:.2f} MB/s")
        if total >= 20 * 1048576:
            break
from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="payu_frappe",
    version="1.0.0",
    description="PayU Payment Gateway + ITR Filing Integration for Frappe",
    author="Aionion Advisory",
    author_email="admin@aionionadvisory.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)

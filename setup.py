from setuptools import setup, find_packages

setup(
    name="quantapy",  # THIS RESERVES THE NAME
    version="0.0.1",
    packages=find_packages(),
    description="QuantaPy library",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/quantafied/quantapy",  # link to GitHub repo
    author="Andrew Simin",
    author_email="contact.quantafied@gmail.com",
    license="Apache-2.0",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)


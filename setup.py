from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="job-pilot",
    version="1.0.0",
    author="Paseka Mabitsela",
    author_email="pasekamabitsela22@gmail.com",
    description="An AI-powered LinkedIn job application automation bot.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/peekay11/job-pilot",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "playwright>=1.40.0",
        "openai>=1.0.0",
        "python-dotenv>=1.0.0"
    ],
    entry_points={
        "console_scripts": [
            "job-pilot=job_pilot.cli:main",
        ],
    },
    python_requires=">=3.10",
)

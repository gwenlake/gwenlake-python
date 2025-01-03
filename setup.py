from setuptools import setup, find_packages

setup(
    name="gwenlake",
    description = "Python client for Gwenlake API",
    version='0.4.1',
    url="https://github.com/gwenlake/gwenlake-python",
    author="The Gwenlake Team",
    author_email="info@gwenlake.com",
    install_requires=["httpx", "pydantic", "pyyaml", "numpy", "pandas", "tiktoken"],
    packages=find_packages(exclude=("tests")),
    python_requires=">=3.11",  # Specify the minimum Python version required
)
from setuptools import setup, find_packages

setup(
    name="gwenlake",
    description = "Python client for Gwenlake API",
    version='0.2.3',
    url="https://github.com/gwenlake/gwenlake-python",
    author="The Gwenlake Team",
    author_email="info@gwenlake.com",
    install_requires=["httpx", "pydantic", "pyyaml", "numpy", "pandas", "tiktoken"],
    packages=find_packages(exclude=('tests', "internal-test")),
    python_requires=">=3.10",  # Specify the minimum Python version required
)
import setuptools,pywebhost

with open("README.md", "r",encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name="pywebhost", # Replace with your own username
    version=pywebhost.__version__,
    author="greats3an",
    author_email="greats3an@gmail.com",
    description="A versatile webserver written in Python 3",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/greats3an/pywebhost",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],install_requires=[],
    python_requires='>=3.6',
)
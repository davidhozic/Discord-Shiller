import setuptools




with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


__metadata__ = \
{
    "version" :  "1.7.9",
    "requirements" :  ["aiohttp>=3.6.0,<3.9.0", "PyNaCl"],
    "minimum_py_version" :  "3.8",
}

setuptools.setup(
    name="Discord-Advert-Framework",
    version=__metadata__["version"],
    author="David Hozic",
    author_email="davidhozic@gmail.com",
    description="Framework (or bot) that allows you to advertise on discord",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/davidhozic/discord-advertisement-framework",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=f">={__metadata__['minimum_py_version']}",
    install_requires=__metadata__["requirements"]
)
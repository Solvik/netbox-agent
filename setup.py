from setuptools import setup, find_packages

setup(
    name='netbox_agent',
    version='0.1',
    description='NetBox agent for server',
    long_description=open('README.md', encoding="utf-8").read(),
    url='https://github.com/solvik/netbox_agent',
    author='Solvik Blum',
    author_email='solvik@solvik.fr',
    license='Apache2',
    include_package_data=True,
    use_scm_version=True,
    packages=find_packages(),
    install_requires=open('requirements.txt').readlines(),
    zip_safe=False,
    keywords=['netbox'],
    classifiers=[
        'Intended Audience :: Developers',
        'Development Status :: 5 - Production/Stable',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    entry_points={
        'console_scripts': ['netbox_agent=netbox_agent.cli:main'],
    }
)

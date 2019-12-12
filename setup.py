from setuptools import setup, find_packages

setup(
    name='netbox_agent',
    version='0.3.1',
    description='NetBox agent for server',
    long_description=open('README.md', encoding="utf-8").read(),
    url='https://github.com/solvik/netbox_agent',
    author='Solvik Blum',
    author_email='solvik@solvik.fr',
    license='Apache2',
    include_package_data=True,
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    use_scm_version=True,
    install_requires=[
        'pynetbox==4.0.8',
        'netaddr==0.7.19',
        'netifaces==0.10.9',
        'pyyaml==5.2',
        'jsonargparse==2.15.0',
        ],
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

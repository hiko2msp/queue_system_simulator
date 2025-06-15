import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as redshift_alpha from '@aws-cdk/aws-redshift-alpha';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as glue_alpha from '@aws-cdk/aws-glue-alpha';
import * as lakeformation from 'aws-cdk-lib/aws-lakeformation'; // For L1 CfnPrincipalPermissions
import * as iam from 'aws-cdk-lib/aws-iam';
// import * as sqs from 'aws-cdk-lib/aws-sqs';

export class AppStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly rawDataBucket: s3.Bucket;
  public readonly auroraCluster: rds.DatabaseCluster;
  public readonly redshiftAdminSecret: secretsmanager.Secret;
  public readonly redshiftNamespace: redshift_alpha.Namespace;
  public readonly redshiftWorkgroup: redshift_alpha.Workgroup;
  public readonly glueDatabase: glue_alpha.Database;
  public readonly lakeFormationS3Role: iam.Role;
  public readonly lfS3RegisteredPath: lakeformation.CfnResource;
  public readonly glueS3CrawlerRole: iam.Role;
  public readonly glueS3Crawler: glue_alpha.Crawler;
  public readonly redshiftDataLakeAccessRole: iam.Role;
  public readonly auroraRedshiftIntegration: rds.CfnIntegration;


  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Define a new VPC
    this.vpc = new ec2.Vpc(this, 'DatalakeVpc', {
      cidr: '10.0.0.0/16',
      maxAzs: 2,
      subnetConfiguration: [
        {
          cidrMask: 24, // Adjust mask as needed for subnet size
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24, // Adjust mask as needed for subnet size
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
        {
          cidrMask: 28, // Smaller CIDR for isolated if needed, adjust as necessary
          name: 'Isolated',
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        }
      ],
      natGateways: 1 // Create one NAT Gateway for the private subnets that need egress
    });

    // Define the S3 bucket for raw data
    this.rawDataBucket = new s3.Bucket(this, 'RawDataBucket', {
      // CDK will generate a unique physical name.
      // You can add a bucketName prefix if desired, e.g., bucketName: 'my-datalake-raw-data-bucket'
      // but ensure it's globally unique or let CDK handle full uniqueness.
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true, // Required if removalPolicy is DESTROY
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    // Output the bucket name
    new cdk.CfnOutput(this, 'RawDataBucketName', {
      value: this.rawDataBucket.bucketName,
      description: 'Name of the S3 bucket for raw data',
    });

    // Define an Aurora MySQL database cluster
    this.auroraCluster = new rds.DatabaseCluster(this, 'AuroraDatalakeCluster', {
      engine: rds.DatabaseClusterEngine.auroraMysql({
        version: rds.AuroraMysqlEngineVersion.VER_3_03_0, // Specify your desired Aurora MySQL version
      }),
      credentials: rds.Credentials.fromGeneratedSecret('MasterUser'), // Manages a secret in Secrets Manager
      instanceProps: {
        instanceType: ec2.InstanceType.of(
          ec2.InstanceClass.BURSTABLE3,
          ec2.InstanceSize.SMALL
        ),
        vpc: this.vpc,
        vpcSubnets: {
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED, // Use isolated subnets for the database
        },
      },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      // For Zero-ETL, you might need to configure a cluster parameter group
      // to enable features like binary logging (e.g., binlog_format = 'ROW').
      // This can be done by creating a new rds.ClusterParameterGroup and associating it.
      // parameterGroup: myClusterParameterGroup,
      // Default security group allows inbound from within the VPC on port 3306.
      // We can refine this later if needed, e.g. for Redshift access.
    });

    // Output the Aurora cluster endpoint and secret ARN
    new cdk.CfnOutput(this, 'AuroraClusterEndpoint', {
      value: this.auroraCluster.clusterEndpoint.hostname,
      description: 'Aurora MySQL Cluster Endpoint',
    });

    if (this.auroraCluster.secret) {
      new cdk.CfnOutput(this, 'AuroraClusterSecretArn', {
        value: this.auroraCluster.secret.secretArn,
        description: 'Aurora MySQL Cluster Secret ARN',
      });
    }

    // Secret for Redshift Admin User
    this.redshiftAdminSecret = new secretsmanager.Secret(this, 'RedshiftAdminPassword', {
      secretName: `${this.stackName}-RedshiftAdminPassword`,
      description: 'Password for the Redshift Serverless admin user',
      generateSecretString: {
        passwordLength: 16,
        excludePunctuation: true,
      },
    });

    // Redshift Serverless Namespace
    this.redshiftNamespace = new redshift_alpha.Namespace(this, 'DatalakeRedshiftNamespace', {
      namespaceName: `${this.stackName}-datalakens`.toLowerCase().replace(/[^a-z0-9]/g, ''), // Ensure compliance with naming rules
      dbName: 'dev',
      adminUsername: 'adminuser',
      adminUserPassword: this.redshiftAdminSecret.secretValue,
      iamRoles: [], // Will be populated later
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Security Group for Redshift Workgroup
    const redshiftSg = new ec2.SecurityGroup(this, 'RedshiftWorkgroupSg', {
      vpc: this.vpc,
      description: 'Security group for Redshift Serverless workgroup',
      allowAllOutbound: true, // Allows egress to S3, Glue, etc.
    });
    // You might want to add specific ingress rules if needed, e.g., from specific IPs or other SGs.

    // Redshift Serverless Workgroup
    this.redshiftWorkgroup = new redshift_alpha.Workgroup(this, 'DatalakeRedshiftWorkgroup', {
      workgroupName: `${this.stackName}-datalakewg`.toLowerCase().replace(/[^a-z0-9]/g, ''), // Ensure compliance
      namespaceName: this.redshiftNamespace.namespaceName,
      baseCapacity: 32,
      subnetIds: this.vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }).subnetIds,
      securityGroupIds: [redshiftSg.securityGroupId],
      publiclyAccessible: false,
      enhancedVpcRouting: true, // Recommended
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      // configParameters: [{ key: 'enable_user_activity_logging', value: 'true' }] // Example config
    });

    // Ensure Workgroup depends on Namespace
    this.redshiftWorkgroup.node.addDependency(this.redshiftNamespace);

    // Outputs for Redshift Serverless
    new cdk.CfnOutput(this, 'RedshiftNamespaceName', {
      value: this.redshiftNamespace.namespaceName,
      description: 'Redshift Serverless Namespace Name',
    });
    new cdk.CfnOutput(this, 'RedshiftWorkgroupName', {
      value: this.redshiftWorkgroup.workgroupName,
      description: 'Redshift Serverless Workgroup Name',
    });
    new cdk.CfnOutput(this, 'RedshiftAdminSecretArnOutput', {
      value: this.redshiftAdminSecret.secretArn,
      description: 'ARN of the Redshift Admin User Password Secret',
    });

    // --- Glue and Lake Formation Setup ---

    // 1. Glue Database
    this.glueDatabase = new glue_alpha.Database(this, 'DatalakeGlueDatabase', {
      databaseName: `${this.stackName}-datalakeglue-db`.toLowerCase().replace(/[^a-z0-9_]/g, '_'),
      // description: 'Glue database for the datalake',
    });

    // 2. IAM Role for Lake Formation to access S3
    this.lakeFormationS3Role = new iam.Role(this, 'LakeFormationS3AccessRole', {
      assumedBy: new iam.ServicePrincipal('lakeformation.amazonaws.com'),
      description: 'Role for Lake Formation to access S3 registered locations',
    });
    this.rawDataBucket.grantReadWrite(this.lakeFormationS3Role); // Grant S3 access to the role

    // 3. Register S3 bucket with Lake Formation
    this.lfS3RegisteredPath = new lakeformation.CfnResource(this, 'RawDataBucketLfResource', {
      resourceArn: this.rawDataBucket.bucketArn,
      roleArn: this.lakeFormationS3Role.roleArn,
      useServiceLinkedRole: false, // Important to use the role we provided
    });
    // Ensure LF role is created before the CfnResource that uses it
    this.lfS3RegisteredPath.node.addDependency(this.lakeFormationS3Role);


    // 4. IAM Role for Glue Crawler
    this.glueS3CrawlerRole = new iam.Role(this, 'GlueS3CrawlerRole', {
      assumedBy: new iam.ServicePrincipal('glue.amazonaws.com'),
      description: 'Role for Glue S3 crawler',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSGlueServiceRole'),
      ],
    });
    this.rawDataBucket.grantRead(this.glueS3CrawlerRole); // Grant S3 read access
    // The AWSGlueServiceRole managed policy includes CloudWatch Logs access.

    // 5. Glue Crawler for S3
    this.glueS3Crawler = new glue_alpha.Crawler(this, 'S3DatalakeCrawler', {
      role: this.glueS3CrawlerRole,
      database: this.glueDatabase,
      targets: {
        s3Targets: [{ path: this.rawDataBucket.s3UrlForObject() }], // Crawl entire bucket
      },
      schemaChangePolicy: {
        updateBehavior: glue_alpha.UpdateBehavior.LOG,
        deleteBehavior: glue_alpha.DeleteBehavior.DEPRECATE_IN_DATABASE,
      },
      name: `${this.stackName}-s3-datalake-crawler`.toLowerCase().replace(/[^a-z0-9_]/g, '_'),
      // configuration: JSON.stringify({ // Example advanced config
      //   "Version":1.0,
      //   "Grouping":{"TableGroupingPolicy":"CombineCompatibleSchemas"},
      //   "CrawlerOutput":{"Partitions":{"AddOrUpdateBehavior":"InheritFromTable"}}
      // })
    });

    // 6. Lake Formation Permissions for Glue Crawler Role
    // Grant LF permissions to the crawler role to access the S3 location
    new lakeformation.CfnPrincipalPermissions(this, 'GlueCrawlerS3LocationPermissions', {
      principal: {
        dataLakePrincipalIdentifier: this.glueS3CrawlerRole.roleArn,
      },
      resource: {
        dataLocation: { // Corrected structure for DataLocationResource
          resourceArn: this.rawDataBucket.bucketArn, // Using bucket ARN for data location
          catalogId: this.account, // AWS Account ID
        },
      },
      permissions: ['DATA_LOCATION_ACCESS'],
    }).node.addDependency(this.lfS3RegisteredPath); // Depends on S3 path being registered

    // Grant LF permissions to the crawler role to create tables in the Glue database
    new lakeformation.CfnPrincipalPermissions(this, 'GlueCrawlerDbPermissions', {
      principal: {
        dataLakePrincipalIdentifier: this.glueS3CrawlerRole.roleArn,
      },
      resource: {
        database: {
          catalogId: this.account, // AWS Account ID
          name: this.glueDatabase.databaseName,
        },
      },
      permissions: ['CREATE_TABLE', 'ALTER', 'DROP'], // Permissions to manage tables
    });


    // 7. IAM Role for Redshift to access Lake Formation protected data
    this.redshiftDataLakeAccessRole = new iam.Role(this, 'RedshiftDataLakeAccessRole', {
      assumedBy: new iam.ServicePrincipal('redshift.amazonaws.com'),
      description: 'Role for Redshift to query data through Lake Formation',
    });
    // Add this role to Redshift Namespace's IAM roles
    this.redshiftNamespace.addIamRole(this.redshiftDataLakeAccessRole);


    // 8. Grant Lake Formation permissions to the Redshift role for the Glue database
    new lakeformation.CfnPrincipalPermissions(this, 'RedshiftDbPermissions', {
      principal: {
        dataLakePrincipalIdentifier: this.redshiftDataLakeAccessRole.roleArn,
      },
      resource: {
        database: {
          catalogId: this.account,
          name: this.glueDatabase.databaseName,
        },
      },
      permissions: ['DESCRIBE'], // Database-level describe
    });

    // Grant Lake Formation permissions to the Redshift role for all tables in the Glue database
    new lakeformation.CfnPrincipalPermissions(this, 'RedshiftTablePermissions', {
      principal: {
        dataLakePrincipalIdentifier: this.redshiftDataLakeAccessRole.roleArn,
      },
      resource: {
        tableWithColumns: { // Granting on all tables within the database
          catalogId: this.account,
          databaseName: this.glueDatabase.databaseName,
          name: '*', // Wildcard for all tables
          columnWildcard: {}, // Grant for all columns
        },
      },
      permissions: ['SELECT', 'DESCRIBE'], // Table-level select & describe
    });


    // --- Stack Outputs ---
    new cdk.CfnOutput(this, 'GlueDatabaseName', {
      value: this.glueDatabase.databaseName,
      description: 'Name of the Glue Database',
    });
    new cdk.CfnOutput(this, 'GlueS3CrawlerName', {
      value: this.glueS3Crawler.name,
      description: 'Name of the Glue S3 Crawler',
    });
    new cdk.CfnOutput(this, 'LakeFormationS3RoleArn', {
      value: this.lakeFormationS3Role.roleArn,
      description: 'ARN of the IAM Role for Lake Formation S3 access',
    });
    new cdk.CfnOutput(this, 'RedshiftDataLakeAccessRoleArn', {
      value: this.redshiftDataLakeAccessRole.roleArn,
      description: 'ARN of the IAM Role for Redshift to access data via Lake Formation',
    });

    // The code that defines your stack goes here

    // --- Zero-ETL Integration between Aurora and Redshift ---
    // Note: Ensure Aurora cluster and Redshift Namespace ARNs are available.
    // The RDS L2 construct for DatabaseCluster (`this.auroraCluster`) exposes `clusterArn`.
    // The Redshift Alpha L2 construct for Namespace (`this.redshiftNamespace`) should expose `namespaceArn` or similar.
    // If `namespaceArn` is not directly available on `this.redshiftNamespace` from the alpha L2,
    // we might need to construct it or use the `namespaceId` to form it.
    // For now, assuming `this.redshiftNamespace.namespaceArn` is available.
    // A common pattern for ARNs if not directly on construct:
    // `arn:${this.partition}:redshift-serverless:${this.region}:${this.account}:namespace/${this.redshiftNamespace.namespaceId}`

    // Check if redshiftNamespace.namespaceArn is available, otherwise construct it.
    // The `@aws-cdk/aws-redshift-alpha.Namespace` construct has `attrNamespaceArn`
    const redshiftNamespaceArn = this.redshiftNamespace.attrNamespaceArn;


    this.auroraRedshiftIntegration = new rds.CfnIntegration(this, 'AuroraRedshiftZeroEtlIntegration', {
      sourceArn: this.auroraCluster.clusterArn,
      targetArn: redshiftNamespaceArn,
      integrationName: `aurora-rs-etl-${this.stackName}`.toLowerCase().replace(/[^a-z0-9-]/g, '-').substring(0, 60), // Max 60 chars
      // kmsKeyId: 'alias/aws/rds', // Optional: Specify a KMS key for the integration
      // additionalEncryptionContext: { // Optional
      //   'ContextKey': 'ContextValue'
      // },
      // tags: [{ key: 'Name', value: 'MyZeroEtlIntegration' }] // Optional
    });

    // Ensure dependencies if not automatically inferred by ARNs
    this.auroraRedshiftIntegration.addDependency(this.auroraCluster.node.defaultChild as cdk.CfnResource);
    // The redshiftNamespace is an L2 alpha, its default child might not be the CfnNamespace directly.
    // A safer way to depend on the L2 construct completing:
    this.auroraRedshiftIntegration.node.addDependency(this.redshiftNamespace);


    new cdk.CfnOutput(this, 'ZeroEtlIntegrationName', {
      value: this.auroraRedshiftIntegration.integrationName,
      description: 'Name of the Zero-ETL Integration between Aurora and Redshift',
    });

    // example resource
    // const queue = new sqs.Queue(this, 'AppQueue', {
    //   visibilityTimeout: cdk.Duration.seconds(300)
    // });
  }
}

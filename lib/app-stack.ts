import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as rds from 'aws-cdk-lib/aws-rds';
// import * as redshift_alpha from '@aws-cdk/aws-redshift-alpha'; // Removed
import * as redshiftserverless from 'aws-cdk-lib/aws-redshiftserverless'; // Added for L1
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as glue_alpha from '@aws-cdk/aws-glue-alpha'; // For Database
import * as glue from 'aws-cdk-lib/aws-glue'; // For Crawler and its enums
import * as lakeformation from 'aws-cdk-lib/aws-lakeformation'; // For L1 CfnPrincipalPermissions
import * as iam from 'aws-cdk-lib/aws-iam';
// import * as sqs from 'aws-cdk-lib/aws-sqs';

export class AppStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly rawDataBucket: s3.Bucket;
  public readonly auroraCluster: rds.DatabaseCluster;
  public readonly redshiftAdminSecret: secretsmanager.Secret;
  public readonly redshiftNamespace: redshiftserverless.CfnNamespace; // Changed to L1
  public readonly redshiftWorkgroup: redshiftserverless.CfnWorkgroup; // Changed to L1
  public readonly glueDatabase: glue_alpha.Database; // Reverted to alpha
  public readonly lakeFormationS3Role: iam.Role;
  public readonly lfS3RegisteredPath: lakeformation.CfnResource;
  public readonly glueS3CrawlerRole: iam.Role;
  public readonly glueS3Crawler: glue.CfnCrawler; // Changed to L1 CfnCrawler
  public readonly redshiftDataLakeAccessRole: iam.Role;
  public readonly auroraRedshiftIntegration: rds.CfnIntegration;
  public readonly quickSightRole: iam.Role;


  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Define a new VPC
    this.vpc = new ec2.Vpc(this, 'DatalakeVpc', {
      ipAddresses: ec2.IpAddresses.cidr('10.0.0.0/16'),
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
      versioned: false, // Changed from true to false as per request
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
        version: rds.AuroraMysqlEngineVersion.VER_3_09_0, // Specify your desired Aurora MySQL version
      }),
      credentials: rds.Credentials.fromGeneratedSecret('MasterUser'), // Manages a secret in Secrets Manager
      vpc: this.vpc, // Moved from instanceProps
      vpcSubnets: { // Moved from instanceProps
        subnetType: ec2.SubnetType.PRIVATE_ISOLATED, // Use isolated subnets for the database
      },
      writer: rds.ClusterInstance.provisioned('WriterInstance', {
        instanceType: ec2.InstanceType.of(
          ec2.InstanceClass.BURSTABLE3,
          ec2.InstanceSize.SMALL
        ),
      }),
      readers: [
        rds.ClusterInstance.provisioned('ReaderInstance1', {
          instanceType: ec2.InstanceType.of(
            ec2.InstanceClass.BURSTABLE3,
            ec2.InstanceSize.SMALL
          ),
        }),
      ],
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

    // IAM Role for Redshift to access Lake Formation protected data (moved before Namespace)
    this.redshiftDataLakeAccessRole = new iam.Role(this, 'RedshiftDataLakeAccessRole', {
      assumedBy: new iam.ServicePrincipal('redshift.amazonaws.com'),
      description: 'Role for Redshift to query data through Lake Formation',
    });

    // Redshift Serverless Namespace
    const namespaceNameForRedshift = `${this.stackName}-datalakens`.toLowerCase().replace(/[^a-z0-9]/g, '');
    this.redshiftNamespace = new redshiftserverless.CfnNamespace(this, 'DatalakeRedshiftNamespace', {
      namespaceName: namespaceNameForRedshift,
      dbName: 'dev',
      adminUsername: 'adminuser',
      adminUserPassword: this.redshiftAdminSecret.secretValue.unsafeUnwrap(), // L1 needs raw string
      iamRoles: [this.redshiftDataLakeAccessRole.roleArn], // Set directly
      // removalPolicy equivalent is handled at stack level or via retain policies
    });

    // Security Group for Redshift Workgroup
    const redshiftSg = new ec2.SecurityGroup(this, 'RedshiftWorkgroupSg', {
      vpc: this.vpc,
      description: 'Security group for Redshift Serverless workgroup',
      allowAllOutbound: true, // Allows egress to S3, Glue, etc.
    });
    // You might want to add specific ingress rules if needed, e.g., from specific IPs or other SGs.

    // Redshift Serverless Workgroup
    const workgroupNameForRedshift = `${this.stackName}-datalakewg`.toLowerCase().replace(/[^a-z0-9]/g, '');
    this.redshiftWorkgroup = new redshiftserverless.CfnWorkgroup(this, 'DatalakeRedshiftWorkgroup', {
      workgroupName: workgroupNameForRedshift,
      namespaceName: this.redshiftNamespace.namespaceName, // Refers to the input prop of CfnNamespace
      baseCapacity: 32, // RPU
      subnetIds: this.vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }).subnetIds,
      securityGroupIds: [redshiftSg.securityGroupId],
      publiclyAccessible: false,
      // enhancedVpcRouting: true, // Not a direct CfnWorkgroup prop; managed by network config
      // removalPolicy equivalent is handled at stack level
      // configParameters: [{ parameterKey: 'enable_user_activity_logging', parameterValue: 'true' }] // L1 uses different structure
    });

    // Ensure Workgroup depends on Namespace - CDK usually infers this if namespaceName is a ref,
    // but explicit dependency is safer for L1 if namespaceName is passed as plain string.
    // However, this.redshiftNamespace.namespaceName is a string token so it should be fine.
    // this.redshiftWorkgroup.addDependency(this.redshiftNamespace.node.defaultChild as cdk.CfnResource); // Alternative if needed

    // --- Consolidated Stack Outputs ---
    // S3
    // RawDataBucketName is already defined earlier

    // Aurora
    // AuroraClusterEndpoint is already defined earlier
    // AuroraClusterSecretArn is already defined earlier (conditional)
    new cdk.CfnOutput(this, 'AuroraClusterIdentifier', {
      value: this.auroraCluster.clusterIdentifier,
      description: 'Aurora MySQL Cluster Identifier',
    });

    // Redshift Serverless
    new cdk.CfnOutput(this, 'RedshiftNamespaceName', {
      value: this.redshiftNamespace.ref, // .ref returns the Name for CfnNamespace
      description: 'Redshift Serverless Namespace Name',
    });
    new cdk.CfnOutput(this, 'RedshiftWorkgroupName', {
      value: this.redshiftWorkgroup.ref, // .ref returns the Name for CfnWorkgroup
      description: 'Redshift Serverless Workgroup Name',
    });
    new cdk.CfnOutput(this, 'RedshiftAdminSecretArn', { // Renamed from RedshiftAdminSecretArnOutput
      value: this.redshiftAdminSecret.secretArn,
      description: 'ARN of the Redshift Admin User Password Secret',
    });

    // 1. Glue Database (Moved before CfnOutput)
    this.glueDatabase = new glue_alpha.Database(this, 'DatalakeGlueDatabase', { // Reverted to alpha
      databaseName: `${this.stackName}-datalakeglue-db`.toLowerCase().replace(/[^a-z0-9_]/g, '_'),
      // description: 'Glue database for the datalake',
    });

    // Glue and Lake Formation
    new cdk.CfnOutput(this, 'GlueDatabaseName', {
      value: this.glueDatabase.databaseName,
      description: 'Name of the Glue Database',
    });
    new cdk.CfnOutput(this, 'GlueCrawlerName', {
      value: this.glueS3Crawler.ref, // .ref returns the name of the crawler for CfnCrawler
      description: 'Name of the Glue S3 Crawler',
    });
    new cdk.CfnOutput(this, 'LakeFormationS3AccessRoleArn', {
      value: this.lakeFormationS3Role.roleArn,
      description: 'ARN of the IAM Role for Lake Formation S3 access',
    });
    new cdk.CfnOutput(this, 'RedshiftDataLakeAccessRoleArn', {
      value: this.redshiftDataLakeAccessRole.roleArn,
      description: 'ARN of the IAM Role for Redshift to access data via Lake Formation',
    });

    // Zero-ETL Integration
    new cdk.CfnOutput(this, 'AuroraRedshiftIntegrationArn', { // Changed from ZeroEtlIntegrationName and value
      value: this.auroraRedshiftIntegration.attrIntegrationArn, // Outputting the ARN
      description: 'ARN of the Zero-ETL Integration between Aurora and Redshift',
    });

    // QuickSight
    new cdk.CfnOutput(this, 'QuickSightAccessRoleArn', { // Renamed from QuickSightRoleArn
      value: this.quickSightRole.roleArn,
      description: 'ARN of the IAM Role for QuickSight access',
    });

    // --- Glue and Lake Formation Setup ---

    // 1. Glue Database - MOVED EARLIER

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
    this.glueS3Crawler = new glue.CfnCrawler(this, 'S3DatalakeCrawler', { // Changed to L1 CfnCrawler
      role: this.glueS3CrawlerRole.roleArn, // L1 needs ARN
      databaseName: this.glueDatabase.databaseName, // L1 needs databaseName string
      targets: {
        s3Targets: [{ path: this.rawDataBucket.s3UrlForObject() }], // Crawl entire bucket
      },
      schemaChangePolicy: { // L1 uses direct strings or specific Property type
        updateBehavior: 'LOG',
        deleteBehavior: 'DEPRECATE_IN_DATABASE',
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
      permissionsWithGrantOption: [],
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
      permissionsWithGrantOption: [],
    });


    // 7. IAM Role for Redshift - definition moved up

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
      permissionsWithGrantOption: [],
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
      permissionsWithGrantOption: [],
    });


    // The code that defines your stack goes here, including resource definitions...
    // ... (previous resource definitions) ...


    // --- Zero-ETL Integration (defined before QuickSight role that might use its output) ---
    const redshiftNamespaceArn = cdk.Fn.getAtt(this.redshiftNamespace.logicalId, 'Namespace.Arn').toString();
    this.auroraRedshiftIntegration = new rds.CfnIntegration(this, 'AuroraRedshiftZeroEtlIntegration', {
      sourceArn: this.auroraCluster.clusterArn,
      targetArn: redshiftNamespaceArn,
      integrationName: `aurora-rs-etl-${this.stackName}`.toLowerCase().replace(/[^a-z0-9-]/g, '-').substring(0, 60),
    });
    this.auroraRedshiftIntegration.addDependency(this.auroraCluster.node.defaultChild as cdk.CfnResource);
    this.auroraRedshiftIntegration.node.addDependency(this.redshiftNamespace);

    // --- IAM Role for QuickSight (defined after resources it references) ---
    this.quickSightRole = new iam.Role(this, 'QuickSightRedshiftLakeFormationAccessRole', {
      assumedBy: new iam.ServicePrincipal('quicksight.amazonaws.com'),
      description: 'IAM Role for QuickSight to access Redshift and Lake Formation governed data',
    });
    const quicksightRedshiftPolicy = new iam.Policy(this, 'QuickSightRedshiftPolicy', { // ... policy statements ...
      statements: [
        new iam.PolicyStatement({
          actions: [
            'redshift-serverless:GetNamespace',
            'redshift-serverless:GetWorkgroup',
          ],
          resources: [
            cdk.Fn.getAtt(this.redshiftNamespace.logicalId, 'Namespace.Arn').toString(),
            cdk.Fn.getAtt(this.redshiftWorkgroup.logicalId, 'Workgroup.Arn').toString(),
          ],
        }),
        new iam.PolicyStatement({
          actions: [
            'redshift-data:ExecuteStatement',
            'redshift-data:DescribeStatement',
            'redshift-data:ListStatements',
            'redshift-data:GetStatementResult',
            'redshift-data:CancelStatement',
          ],
          resources: [
            `arn:aws:redshift-serverless:${this.region}:${this.account}:workgroup/${cdk.Fn.getAtt(this.redshiftWorkgroup.logicalId, 'Workgroup.WorkgroupId').toString()}`,
             cdk.Fn.getAtt(this.redshiftWorkgroup.logicalId, 'Workgroup.Arn').toString(),
             `${cdk.Fn.getAtt(this.redshiftWorkgroup.logicalId, 'Workgroup.Arn').toString()}/*`,
             cdk.Fn.getAtt(this.redshiftNamespace.logicalId, 'Namespace.Arn').toString(),
             `${cdk.Fn.getAtt(this.redshiftNamespace.logicalId, 'Namespace.Arn').toString()}/*`,
          ],
        }),
      ],
    });
    this.quickSightRole.attachInlinePolicy(quicksightRedshiftPolicy);
    const quicksightLakeFormationPolicy = new iam.Policy(this, 'QuickSightLakeFormationPolicy', { // ... policy statements ...
       statements: [
        new iam.PolicyStatement({
          actions: ['lakeformation:GetDataAccess'],
          resources: ['*'],
        }),
        new iam.PolicyStatement({
          actions: [
            'glue:GetDatabase',
            'glue:GetDatabases',
            'glue:GetTable',
            'glue:GetTables',
            'glue:GetPartitions',
            'glue:SearchTables',
          ],
          resources: [
            this.glueDatabase.databaseArn,
            `arn:aws:glue:${this.region}:${this.account}:catalog`,
            `arn:aws:glue:${this.region}:${this.account}:table/${this.glueDatabase.databaseName}/*`,
          ],
        }),
        new iam.PolicyStatement({
            actions: ['lakeformation:GetLFTag', 'lakeformation:SearchTablesByLFTags', 'lakeformation:SearchDatabasesByLFTags'],
            resources: ['*'],
        }),
      ],
    });
    this.quickSightRole.attachInlinePolicy(quicksightLakeFormationPolicy);
    new lakeformation.CfnPrincipalPermissions(this, 'QuickSightLfDbPermissions', {
        principal: { dataLakePrincipalIdentifier: this.quickSightRole.roleArn },
        resource: { database: { catalogId: this.account, name: this.glueDatabase.databaseName } },
        permissions: ['DESCRIBE'],
        permissionsWithGrantOption: [],
    });
    new lakeformation.CfnPrincipalPermissions(this, 'QuickSightLfTablePermissions', {
        principal: { dataLakePrincipalIdentifier: this.quickSightRole.roleArn },
        resource: { tableWithColumns: { catalogId: this.account, databaseName: this.glueDatabase.databaseName, name: "*", columnWildcard: {} } },
        permissions: ['SELECT', 'DESCRIBE'],
        permissionsWithGrantOption: [],
    });


    // Ensure all other CfnOutputs are defined here, at the end or after their resources.
    // example resource (commented out)
    // const queue = new sqs.Queue(this, 'AppQueue', {
    //   visibilityTimeout: cdk.Duration.seconds(300)
    // });
  }
}
